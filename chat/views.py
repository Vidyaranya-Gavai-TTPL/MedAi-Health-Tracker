from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import ChatMessage
import google.generativeai as genai
import os
import base64
from io import BytesIO
import json
import logging

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

@login_required
def chat(request):
    messages = ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:50]
    return render(request, 'chat/chat.html', {
        'messages': messages,
        'api_key': os.getenv('GEMINI_API_KEY', '')
    })

@csrf_exempt
@require_POST
@login_required
def send_message(request):
    try:
        if not model:
            return JsonResponse({'error': 'Gemini API not configured'}, status=500)
            
        data = json.loads(request.body)
        message_type = data.get('type')
        content = data.get('content')
        
        logger.info(f"Received message: {content}")
        
        if not content:
            return JsonResponse({'error': 'No content provided'}, status=400)
        
        # Process the message based on type
        if message_type == 'text':
            try:
                response = model.generate_content(content)
                logger.info(f"Gemini response: {response.text}")
            except Exception as e:
                logger.error(f"Error generating content: {str(e)}")
                return JsonResponse({'error': f'Error generating content: {str(e)}'}, status=500)
        elif message_type == 'image':
            # Handle image processing
            image_data = content.split(',')[1]  # Remove data:image/jpeg;base64,
            image_bytes = base64.b64decode(image_data)
            image = genai.types.Image.from_bytes(image_bytes)
            response = model.generate_content([image, "What's in this image?"])
        elif message_type == 'audio':
            # Handle audio processing
            audio_data = content.split(',')[1]  # Remove data:audio/wav;base64,
            audio_bytes = base64.b64decode(audio_data)
            # Process audio with Gemini (implementation depends on Gemini's audio capabilities)
            response = model.generate_content("Process this audio: [Audio content]")
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
