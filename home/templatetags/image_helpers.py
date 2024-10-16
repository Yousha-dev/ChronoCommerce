import json
from django import template
import os

from django.conf import settings

register = template.Library()

@register.filter
def get_first_image(product):
    print("get_first_image called")  # Debug print statement
    try:
        # Get the first official image related to the product
        imageModel = product.images.first()
        
        if imageModel:
            image_files = json.loads(imageModel.images)
            # If there are image files, return the name of the first one
            if image_files:
                return image_files[0]
    except FileNotFoundError:
        print("FileNotFoundError")  # Debug print statement
        pass
    return 'abc.jpg'