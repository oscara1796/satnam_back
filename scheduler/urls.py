from django.urls import path
from .views import EventViewSet

urlpatterns = [
    path('api/events/', EventViewSet.as_view({'get': 'list', 'post': 'create'}), name='events'),
    path('api/events/<int:pk>/', EventViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='event'),
]