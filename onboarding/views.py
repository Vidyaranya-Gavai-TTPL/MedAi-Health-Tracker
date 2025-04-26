from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import OnboardingQuestion, OnboardingAnswer
import json

# Create your views here.

@login_required
def onboarding(request):
    if request.method == 'POST':
        # Get all questions
        questions = OnboardingQuestion.objects.all().order_by('order')
        
        # Process answers
        for question in questions:
            answer = request.POST.get(f'question_{question.id}')
            if answer:
                OnboardingAnswer.objects.update_or_create(
                    user=request.user,
                    question=question,
                    defaults={'answer': answer}
                )
        
        messages.success(request, 'Onboarding completed successfully!')
        return redirect('medical_assistant')
    
    # Get all questions
    questions = OnboardingQuestion.objects.all().order_by('order')
    
    # Get existing answers
    answers = {
        answer.question_id: answer.answer
        for answer in OnboardingAnswer.objects.filter(user=request.user)
    }
    
    return render(request, 'onboarding/onboarding.html', {
        'questions': questions,
        'answers': answers
    })

@login_required
def edit_onboarding(request):
    if request.method == 'POST':
        # Get all questions
        questions = OnboardingQuestion.objects.all().order_by('order')
        
        # Process answers
        for question in questions:
            answer = request.POST.get(f'question_{question.id}')
            if answer:
                OnboardingAnswer.objects.update_or_create(
                    user=request.user,
                    question=question,
                    defaults={'answer': answer}
                )
        
        messages.success(request, 'Onboarding information updated successfully!')
        return redirect('profile')
    
    # Get all questions
    questions = OnboardingQuestion.objects.all().order_by('order')
    
    # Get existing answers
    answers = {
        answer.question_id: answer.answer
        for answer in OnboardingAnswer.objects.filter(user=request.user)
    }
    
    return render(request, 'onboarding/edit_onboarding.html', {
        'questions': questions,
        'answers': answers
    })
