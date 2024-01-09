from django.http import HttpResponse
from captcha.image import ImageCaptcha
import random
import string
import io

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class ValidateCaptcha(APIView):
    def post(self, request):
        dir(request)

      
        print("Session ID in ValidateCaptcha:", request.session.session_key)
        print("Session Data in ValidateCaptcha:", request.session.items())
        user_captcha = request.data.get('captcha')
        real_captcha = request.session.get('captcha')
        print(user_captcha, real_captcha)
        if not real_captcha or user_captcha != real_captcha:
            return Response({"error": "Invalid CAPTCHA"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"success": "CAPTCHA validated successfully"})

def generate_captcha_text(length=5):
    return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=length))

def captcha_image(request):
    # Generate CAPTCHA text
    captcha_text = generate_captcha_text()

    # Store the text in the session for validation
    request.session['captcha'] = captcha_text

    request.session.modified = True
   
    request.session.save()
    
    print("Session ID in captcha_image:", request.session.session_key)
    print("Session Data in captcha_image:", request.session.items())

    # Define the size of the image
    image_width = 240
    image_height = 100

    # Create an ImageCaptcha instance with the specified size
    image = ImageCaptcha(width=image_width, height=image_height)

    # Generate the CAPTCHA image
    data = image.generate(captcha_text)

    # Convert the ImageCaptcha data to a bytes buffer for HttpResponse
    buffer = io.BytesIO(data.getvalue())

    # Return the image in the response
    return HttpResponse(buffer.getvalue(), content_type="image/png")
