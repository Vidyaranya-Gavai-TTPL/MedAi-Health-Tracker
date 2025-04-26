# forms.py
from django import forms

class FoodInputForm(forms.Form):
    """
    Form for uploading food via text input (food name) or image upload.
    """
    text_input = forms.CharField(max_length=255, required=False, label="Food Name")
    image_input = forms.ImageField(required=False, label="Upload Image")

