from django.db import models
from django.conf import settings
from users.models import User
# Create your models here.

class ChatMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=20)  # text, image, audio
    content = models.TextField()
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.message_type} - {self.created_at}"


class Food(models.Model):
    name = models.CharField(max_length=100, unique=True)
    portion_size = models.IntegerField(null=True, blank=True, default=0)
    calories = models.FloatField(null=True, blank=True)
    protein = models.FloatField(null=True, blank=True)  # in grams
    fat = models.FloatField(null=True, blank=True)      # in grams
    carbs = models.FloatField(null=True, blank=True)    # in grams,


class UserFoodLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    input_text = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='food_images/', null=True, blank=True)

