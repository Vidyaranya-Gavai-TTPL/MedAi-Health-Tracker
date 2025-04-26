# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from chat.models import Food, UserFoodLog
from chat.forms import FoodInputForm
from PIL import Image
import requests
from transformers import pipeline
import os
from django.shortcuts import get_object_or_404
from datetime import timedelta
from datetime import timedelta



@login_required
def food_upload_view(request):
    """
    View to upload food via text or image input, fetch macronutrients, and log the food.
    Returns JSON response indicating success or error.
    """
    if request.method == 'POST':
        form = FoodInputForm(request.POST, request.FILES)
        if form.is_valid():
            api_key = os.getenv('NINJA_API_KEY')  # Load from environment or settings
            input_text = form.cleaned_data.get('text_input')
            image = form.cleaned_data.get('image_input')

            # Detect food from text input or image
            if input_text:
                query = input_text
            elif image:
                # Save the image temporarily and classify
                img = Image.open(image)
                classifier = pipeline("image-classification", model="rajistics/finetuned-indian-food")
                result = classifier(img)[0]
                query = result['label']
            else:
                return JsonResponse({"error": "Please provide either text or image input."}, status=400)

            # Call the API to get macros
            response = requests.get(
                f'https://api.api-ninjas.com/v1/nutrition?query={query}',
                headers={'X-Api-Key': api_key}
            )
            if response.status_code == 200 and response.json():
                macro = response.json()[0]

                # Create a food object or get existing
                food_obj, _ = Food.objects.get_or_create(
                    name=macro['name'],
                    defaults={
                        'calories': macro.get('calories'),
                        'protein': macro.get('protein_g'),
                        'fat': macro.get('fat_total_g'),
                        'carbs': macro.get('carbohydrates_total_g')
                    }
                )

                # Save user log
                log = UserFoodLog.objects.create(
                    user=request.user,
                    food=food_obj,
                    image=image if image else None,
                    input_text=input_text if input_text else None
                )

                return JsonResponse({
                    "success": True,
                    "message": f"Logged {food_obj.name} for {request.user.username}!",
                    "macros": {
                        'calories': macro.get('calories'),
                        'protein_g': macro.get('protein_g'),
                        'fat_g': macro.get('fat_total_g'),
                        'carbs_g': macro.get('carbohydrates_total_g')
                    }
                })

            else:
                return JsonResponse({"error": "Nutrition data not found for the given food."}, status=404)

        else:
            return JsonResponse({"error": "Invalid form data."}, status=400)

    return JsonResponse({"error": "Invalid request method. Use POST to submit the form."}, status=405)

@login_required
def food_history_view(request):
    """
    View to return the user's food history for the last 7 days.
    """
    try:
        # Get the date 7 days ago
        seven_days_ago = timezone.now() - timedelta(days=7)

        # Fetch all food logs for the current user within the last 7 days
        food_logs = UserFoodLog.objects.filter(
            user=request.user,
            date__gte=seven_days_ago
        ).select_related('food')

        # Prepare the response data
        food_history = []
        for log in food_logs:
            food_history.append({
                'food_name': log.food.name,
                'calories': log.food.calories,
                'protein_g': log.food.protein,
                'fat_g': log.food.fat,
                'carbs_g': log.food.carbs,
                'date': log.date.strftime('%Y-%m-%d'),
                'input_text': log.input_text,
                'image': log.image.url if log.image else None
            })

        return JsonResponse({
            "success": True,
            "food_history": food_history
        })

    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)