from django.db import models
from django.conf import settings

# Create your models here.

class OnboardingQuestion(models.Model):
    question = models.CharField(max_length=255)
    question_type = models.CharField(max_length=50)  # text, number, choice, etc.
    required = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.question

class OnboardingAnswer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(OnboardingQuestion, on_delete=models.CASCADE)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'question')

    def __str__(self):
        return f"{self.user.username} - {self.question.question}"
