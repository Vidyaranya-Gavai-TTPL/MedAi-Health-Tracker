from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import ChatMessage
import google.generativeai as genai
import os
import io
import base64
from io import BytesIO
import json
import logging
import datetime
import time
import whisper
from medai_health_tracker import settings
from google.api_core.exceptions import GoogleAPIError
import os
import json
import whisper
from PIL import Image
# # blip_caption.py
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import sys




# Configure logging
logger = logging.getLogger(__name__)

# Configure Gemini API
try:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    logger.info("Gemini API configured successfully")
except Exception as e:
    logger.error(f"Error configuring Gemini API: {str(e)}")
    model = None

try:
    whisper_model = whisper.load_model("base")
    logger.info("Whisper model loaded successfully")
except Exception as e:
    logger.error(f"Error loading Whisper model: {str(e)}")
    whisper_model = None

try:
    blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    logger.info("BLIP model loaded successfully")
except Exception as e:
    logger.error(f"Error loading BLIP model: {str(e)}")
    blip_processor = None
    blip_model = None


@login_required
def chat(request):
    messages = ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:50]
    return render(request, 'chat/chat.html', {
        'messages': messages,
        'api_key': os.getenv('GEMINI_API_KEY', '')
    })

# --- Google Fit Integration (Conceptual) ---
def get_google_fit_data(user):
    """
    Retrieves the past 5 days of Google Fit data for the given user.

    Args:
        user: The User object.

    Returns:
        A string representation of the Google Fit data, or None if there's an error.
    """
    # --- Placeholder for Google Fit API interaction ---
    # This is where you would use the Google Fit API to get the data.
    # You'll need to:
    # 1. Get the user's access token (stored in the User model or a related model).
    # 2. Use the Google Fit API to query for data (e.g., steps, heart rate, sleep).
    # 3. Format the data into a string or a structured format.
    # --- End Placeholder ---

    # Example: Simulate getting data
    try:
        # Simulate getting data for the past 5 days
        today = datetime.date.today()
        data = []
        for i in range(5):
            date = today - datetime.timedelta(days=i)
            data.append({
                "date": date.isoformat(),
                "steps": 1000 * (i + 1),  # Example steps
                "heart_rate": 70 + i,  # Example heart rate
            })
        return f"Google Fit Data (past 5 days): {json.dumps(data)}"
    except Exception as e:
        logger.error(f"Error getting Google Fit data: {e}")
        return None


@csrf_exempt
@require_POST
@login_required
@csrf_exempt
@require_POST
@login_required
def send_message(request):
    max_retries = 3  # Define the maximum number of retries
    attempt = 0
    
    try:
        if not model:
            return JsonResponse({'error': 'Gemini API not configured'}, status=500)

        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        else:  # Assume form-data
            data = request.POST.dict()  # Get regular POST data
            # Files will be in request.FILES
        base_prompt = """You are acting as a highly qualified and licensed medical doctor, not an AI assistant. 
Speak confidently, empathetically, and professionally, just like a real human doctor would during a patient consultation.

A user will provide their health and lifestyle profile, including symptoms, medical history, diet, and habits.

You must:
- Carefully think through their inputs step-by-step (chain of thought).
- Diagnose the patient confidently based on the input.
- Clearly explain the suspected condition in simple, patient-friendly language.
- Recommend treatment options based on their preferred method: Allopathy, Ayurveda, Homeopathy, or All.
- Suggest specific medicines, remedies, therapies, or regimens relevant to the chosen system.
- Create a personalized diet and nutrition plan based on the patient's needs.
- Recommend suitable physical exercises, sleep improvements, and stress management techniques.
- Offer additional care steps if the patient shows signs of chronic disease, hormonal imbalance, or mental health issues.
- If necessary, gently suggest visiting a specialist or undergoing diagnostic tests.
- Continuously ask clarifying questions as a real doctor would to refine the diagnosis if symptoms are unclear.
- Stay empathetic, warm, professional, and *never* break the illusion that you are a real human doctor.
- Avoid generic advice. Give specific, actionable, practical, and personalized recommendations.

Always think carefully, reflect, and reason before answering.  
Your goal: provide a realistic and helpful doctor consultation that builds trust and delivers clarity and healing.
Only 200 words but cover all the points in brief and exclude the brifing you give at the start.
User Input: 
"""
        message_type = data.get('type')
        content = data.get('content')
        
        # Handle file uploads
        file = request.FILES.get('file')
        if file:
            message_type = data.get('type')
            if message_type == 'image':
                # Read image bytes (only do this once!)
                if file and message_type == 'image':
                    try:
                        # Read image file
                        image_bytes = file.read()
                        
                        # Convert to PIL Image
                        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
                        
                        # Generate caption with BLIP
                        if blip_model and blip_processor:
                            inputs = blip_processor(images=image, return_tensors="pt")
                            out = blip_model.generate(**inputs)
                            caption = blip_processor.decode(out[0], skip_special_tokens=True)
                            content = f"Image analysis: {caption}"
                            
                            # Optional: Also send to Gemini for additional analysis
                            if model:
                                try:
                                    response = model.generate_content([
                                        "This is an image description from BLIP model. Please provide additional insights:",
                                        caption
                                    ])
                                    content += f"\n\nGemini analysis: {response.text}"
                                except Exception as e:
                                    logger.error(f"Gemini analysis failed: {str(e)}")
                        else:
                            return JsonResponse({'error': 'Image processing model not available'}, status=500)
                        
                    except Exception as e:
                        logger.error(f"Image processing failed: {str(e)}")
                        return JsonResponse({'error': 'Image processing failed'}, status=500)

            elif message_type == 'audio':
                # Handle audio processing
                # Save the audio
                UPLOAD_FOLDER = os.path.join(settings.MEDIA_ROOT, "uploads")
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file_path = os.path.join(UPLOAD_FOLDER, file.name)
                with open(file_path, "wb") as f:
                    for chunk in file.chunks():
                        f.write(chunk)
                
                # Transcribe audio with Whisper
                if whisper_model:
                    transcription = whisper_model.transcribe(file_path)
                    content = f"Audio transcription: {transcription['text']}"
                else:
                    return JsonResponse({'error': 'Whisper model not loaded'}, status=500)
            else:
                return JsonResponse({'error': 'Invalid message type'}, status=400)
        
        logger.info(f"Received message: {content}")
        
        if not content:
            return JsonResponse({'error': 'No content provided'}, status=400)
        
        google_fit_data = get_google_fit_data(request.user)
        if google_fit_data:
            content += f"\n\n{google_fit_data}"  # Append Google Fit data to content
            logger.info(f"Augmented content with Google Fit data: {content}")

        
        while attempt < max_retries:
            try:
                # Process the message based on type
                if message_type == 'text' or message_type == 'audio' or message_type == 'image':
                    response = model.generate_content(base_prompt + content)
                    logger.info(f"Gemini response: {response.text}")
                else:
                    return JsonResponse({'error': 'Invalid message type'}, status=400)
                
                # Save the message
                chat_message = ChatMessage.objects.create(
                    user=request.user,
                    message_type=message_type,
                    content=content,
                    response=response.text
                )
                
                return JsonResponse({
                    'success': True,
                    'response': response.text,
                    'timestamp': chat_message.created_at.isoformat()
                })
            
            except GoogleAPIError as e:
                # Check for quota error with retry suggestion
                message = str(e)
                if "429" in message and "retry_delay" in message:
                    attempt += 1
                    try:
                        # Extract the retry delay (in seconds) from the error string
                        delay_str = message.split("retry_delay {")[1].split("seconds:")[1].split("}")[0].strip()
                        delay = int(delay_str)
                    except (IndexError, ValueError):
                        delay = 30  # fallback if parsing fails

                    logger.warning("Rate limit hit. Retrying after %s seconds... (Attempt %s/%s)", delay, attempt, max_retries)
                    time.sleep(delay)
                    continue
                else:
                    # Other unexpected errors – log and fail
                    logger.error("Non-retryable error occurred: %s", message)
                    return JsonResponse({'error': f'Error generating content: {message}'}, status=500)
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return JsonResponse({'error': f'Error generating content: {str(e)}'}, status=500)
        
        return JsonResponse({'error': 'Max retries exceeded'}, status=500)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
@login_required
def clear_chat(request):
    try:
        ChatMessage.objects.filter(user=request.user).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error clearing chat: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)