from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('complete/google-oauth2/', views.google_auth_complete, name='google_auth_complete'),
    path('medical-assistant/', views.MedicalAssistantView.as_view(), name='medical_assistant'),
] 