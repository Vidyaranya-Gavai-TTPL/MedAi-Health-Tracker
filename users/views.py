from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .forms import UserRegistrationForm, UserLoginForm
from .models import User
import os
import json
import uuid
import whisper
import pyttsx3
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger(__name__)

def register(request):
    if request.user.is_authenticated:
        return redirect('onboarding')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('onboarding')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'users/register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated:
        return redirect('onboarding')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('onboarding')
    else:
        form = UserLoginForm()
    
    return render(request, 'users/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

@login_required
def profile(request):
    if request.method == 'POST':
        user = request.user
        if 'profile_image' in request.FILES:
            user.profile_image = request.FILES['profile_image']
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    
    return render(request, 'users/profile.html')

def google_auth_complete(request):
    if request.user.is_authenticated:
        # Store Google Fit token
        social = request.user.social_auth.get(provider='google-oauth2')
        request.user.google_fit_token = social.extra_data
        request.user.save()
        return redirect('onboarding')
    return redirect('login')

# Medical questionnaire
MEDICAL_QUESTIONS = [
    "Can you tell me your age, gender, and general health background?",
    "Do you have any existing medical conditions or allergies?",
    "Is there family history of chronic conditions?",
    "What kind of work do you do?",
    "How many hours do you work daily?",
    "What is your typical daily routine?",
    "How would you rate your sleep quality?",
    "What kind of physical activity do you do?",
    "Do you have any current symptoms?",
    "Have you tried any treatments before?",
    "What does your usual daily diet look like?",
    "Do you experience stress or mood swings?",
    "Do you use any health trackers?",
    "What are your current health goals?"
]

@method_decorator(login_required, name='dispatch')
class MedicalAssistantView(View):
    template_name = 'users/medical_assistant.html'
    
    def __init__(self):
        self.upload_folder = os.path.join(settings.MEDIA_ROOT, "uploads")
        os.makedirs(self.upload_folder, exist_ok=True)
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.whisper_model = whisper.load_model("base")
        self.tts_engine = self._init_tts_engine()
        logger.info("MedicalAssistantView initialized")
    
    def _init_tts_engine(self):
        """Initialize text-to-speech engine"""
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        
        # Find a female voice
        for voice in voices:
            if 'female' in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        
        # Set voice properties
        engine.setProperty('rate', 150)  # Slightly slower for clarity
        engine.setProperty('volume', 0.9)
        engine.setProperty('pitch', 1.1)  # Slightly higher pitch for female voice
        
        return engine

    def _format_response(self, text):
        """Format the response text for better readability"""
        # Add pauses between sentences
        text = text.replace('.', '. ')
        text = text.replace('?', '? ')
        text = text.replace('!', '! ')
        
        # Add emphasis to important parts
        if 'diagnosis' in text.lower():
            text = text.replace('Diagnosis:', '\nDiagnosis:')
        if 'treatment plan' in text.lower():
            text = text.replace('Treatment plan:', '\nTreatment plan:')
        if 'diet recommendations' in text.lower():
            text = text.replace('Diet recommendations:', '\nDiet recommendations:')
        if 'lifestyle changes' in text.lower():
            text = text.replace('Lifestyle changes:', '\nLifestyle changes:')
        
        return text

    def _split_text(self, text):
        """Split text into natural sentence chunks"""
        sentences = []
        current_sentence = ""
        for char in text:
            current_sentence += char
            if char in '.!?;':
                sentences.append(current_sentence.strip())
                current_sentence = ""
        if current_sentence:
            sentences.append(current_sentence.strip())
        return [s for s in sentences if s]
    
    def _text_to_speech(self, text):
        """Convert text to speech with proper chunk handling"""
        try:
            # Format the text for better speech
            formatted_text = self._format_response(text)
            chunks = self._split_text(formatted_text)
            audio_files = []
            
            for chunk in chunks:
                filename = f"response_{uuid.uuid4()}.mp3"
                filepath = os.path.join(self.upload_folder, filename)
                
                try:
                    self.tts_engine.save_to_file(chunk, filepath)
                    self.tts_engine.runAndWait()
                    
                    if os.path.exists(filepath):
                        # Create a relative path for the URL
                        relative_path = os.path.join('uploads', filename)
                        audio_files.append(f"/media/{relative_path}")
                        logger.info(f"Generated audio file: {relative_path}")
                    else:
                        logger.error(f"Failed to generate audio file: {filepath}")
                except Exception as e:
                    logger.error(f"Error generating audio for chunk: {str(e)}")
                    continue
            
            return audio_files
        except Exception as e:
            logger.error(f"Error in text-to-speech: {str(e)}")
            return []
    
    def _get_ai_response(self, messages):
        """Get response from DeepSeek via OpenRouter"""
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek/deepseek-r1:free",
                    "messages": messages,
                    "temperature": 0.7
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            print(f"AI API error: {str(e)}")
            return "I encountered an error processing your medical information. Please try again."
    
    def _get_conversations(self, request):
        """Get conversations from session or initialize if not exists"""
        if 'conversations' not in request.session:
            request.session['conversations'] = {}
        return request.session['conversations']
    
    def _get_user_profiles(self, request):
        """Get user profiles from session or initialize if not exists"""
        if 'user_profiles' not in request.session:
            request.session['user_profiles'] = {}
        return request.session['user_profiles']
    
    def _save_conversations(self, request, conversations):
        """Save conversations to session"""
        request.session['conversations'] = conversations
        request.session.modified = True
    
    def _save_user_profiles(self, request, user_profiles):
        """Save user profiles to session"""
        request.session['user_profiles'] = user_profiles
        request.session.modified = True
    
    def get(self, request):
        """Render the main page"""
        logger.info("GET request received for medical assistant")
        return render(request, self.template_name, {
            'MEDICAL_QUESTIONS': MEDICAL_QUESTIONS,
            'MEDICAL_QUESTIONS_JSON': json.dumps(MEDICAL_QUESTIONS)
        })
    
    def post(self, request):
        """Handle API requests"""
        logger.info("POST request received for medical assistant")
        if not request.user.is_authenticated:
            logger.warning("Unauthorized access attempt")
            return JsonResponse({'error': 'Authentication required'}, status=401)
            
        action = request.POST.get('action')
        logger.info(f"Action received: {action}")
        
        if action == 'start_conversation':
            return self._start_conversation(request)
        elif action == 'send_voice':
            return self._handle_voice_message(request)
        else:
            logger.error(f"Invalid action received: {action}")
            return JsonResponse({'error': 'Invalid action'}, status=400)
    
    def _start_conversation(self, request):
        """Start a new conversation"""
        logger.info("Starting new conversation")
        try:
            conversations = self._get_conversations(request)
            user_profiles = self._get_user_profiles(request)
            
            conversation_id = str(uuid.uuid4())
            conversations[conversation_id] = []
            user_profiles[conversation_id] = {
                "question_index": 0, 
                "answers": {},
                "user_id": request.user.id
            }
            
            ai_response = "Welcome to your medical consultation. Let's begin with some questions about your health. " + MEDICAL_QUESTIONS[0]
            ai_audio_files = self._text_to_speech(ai_response)
            conversations[conversation_id].append({
                "role": "assistant",
                "content": ai_response,
                "audio_files": ai_audio_files
            })
            
            self._save_conversations(request, conversations)
            self._save_user_profiles(request, user_profiles)
            
            logger.info(f"Conversation started successfully with ID: {conversation_id}")
            return JsonResponse({
                "conversation_id": conversation_id,
                "ai_response": ai_response,
                "ai_audio": ai_audio_files,
                "current_question": MEDICAL_QUESTIONS[0],
                "question_index": 0
            })
        except Exception as e:
            logger.error(f"Error starting conversation: {str(e)}")
            return JsonResponse({'error': 'Failed to start conversation'}, status=500)
    
    def _handle_voice_message(self, request):
        """Process voice message and respond"""
        logger.info("Handling voice message")
        try:
            conversations = self._get_conversations(request)
            user_profiles = self._get_user_profiles(request)
            
            conversation_id = request.POST.get('conversation_id')
            audio_file = request.FILES.get('audio')
            
            if not conversation_id or conversation_id not in conversations:
                logger.error(f"Invalid conversation ID: {conversation_id}")
                return JsonResponse({'error': 'Invalid conversation'}, status=400)
            if not audio_file:
                logger.error("No audio file provided")
                return JsonResponse({'error': 'No audio file provided'}, status=400)
            
            # Save user audio
            filename = f"user_{uuid.uuid4()}.webm"
            filepath = os.path.join(self.upload_folder, filename)
            with open(filepath, 'wb') as f:
                for chunk in audio_file.chunks():
                    f.write(chunk)
            
            # Transcribe
            logger.info("Transcribing audio")
            user_text = self.whisper_model.transcribe(filepath)["text"]
            logger.info(f"Transcription: {user_text}")
            
            # Store answer
            profile = user_profiles[conversation_id]
            current_index = profile["question_index"]
            profile["answers"][MEDICAL_QUESTIONS[current_index]] = user_text
            profile["question_index"] += 1
            
            # Check if questionnaire complete
            if profile["question_index"] >= len(MEDICAL_QUESTIONS):
                logger.info("Questionnaire complete, generating diagnosis")
                # Save answers to user's onboarding_data
                user = User.objects.get(id=profile["user_id"])
                user.onboarding_data = profile["answers"]
                user.save()
                
                # Generate diagnosis
                profile_text = "\n".join([f"Q: {q}\nA: {profile['answers'][q]}" for q in MEDICAL_QUESTIONS])
                ai_response = self._get_ai_response([
                    {
                        "role": "system",
                        "content": "You are a medical doctor. Analyze this patient profile and provide: "
                                   "1. Diagnosis, 2. Treatment plan, 3. Diet recommendations, 4. Lifestyle changes. "
                                   "Be specific about medications, exercises, and daily routines."
                    },
                    {
                        "role": "user",
                        "content": profile_text
                    }
                ])
            else:
                # Ask next question
                next_question = MEDICAL_QUESTIONS[profile["question_index"]]
                ai_response = next_question
            
            # Generate audio for the response
            try:
                ai_audio_files = self._text_to_speech(ai_response)
                if not ai_audio_files:
                    logger.warning("No audio files generated for response")
            except Exception as e:
                logger.error(f"Error generating audio: {str(e)}")
                ai_audio_files = []
            
            # Store messages
            conversations[conversation_id].extend([
                {
                    "role": "user",
                    "content": user_text,
                    "audio_files": [f"/media/uploads/{filename}"]
                },
                {
                    "role": "assistant",
                    "content": ai_response,
                    "audio_files": ai_audio_files
                }
            ])
            
            self._save_conversations(request, conversations)
            self._save_user_profiles(request, user_profiles)
            
            logger.info("Voice message processed successfully")
            return JsonResponse({
                "user_message": user_text,
                "ai_response": ai_response,
                "ai_audio": ai_audio_files,
                "current_question": MEDICAL_QUESTIONS[profile["question_index"]] if profile["question_index"] < len(MEDICAL_QUESTIONS) else None,
                "question_index": profile["question_index"]
            })
        except Exception as e:
            logger.error(f"Error processing voice message: {str(e)}")
            return JsonResponse({'error': 'Failed to process voice message'}, status=500)
