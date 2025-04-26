from django.urls import path
from . import views
from .utils import food_handler 

urlpatterns = [
    path('', views.chat, name='chat'),
    path('send/', views.send_message, name='send_message'),
    path('clear/', views.clear_chat, name='clear_chat'),
    path('food/upload/', food_handler.food_upload_view, name='food_upload'),
    path('food/list/', food_handler.food_upload_view, name='food_upload'),
] 