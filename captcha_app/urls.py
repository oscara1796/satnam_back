from django.urls import path
from . import views

urlpatterns = [
    path('api/get-captcha/', views.captcha_image, name='captcha_image'),
    path('api/captcha/', views.ValidateCaptcha.as_view(), name='captcha_validation'),
]
