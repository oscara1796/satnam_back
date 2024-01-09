from django.urls import path
from .views import ContactSubmissionView

urlpatterns = [
    path('api/contact/', ContactSubmissionView.as_view(), name='contacts'),
    path('api/contact/<int:pk>/', ContactSubmissionView.as_view(), name='contact'),
]
