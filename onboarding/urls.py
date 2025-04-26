from django.urls import path
from . import views

urlpatterns = [
    path('', views.onboarding, name='onboarding'),
    path('edit/', views.edit_onboarding, name='edit_onboarding'),
] 