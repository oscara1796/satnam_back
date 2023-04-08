from django.urls import path 
from .views import VideoList, VideoDetail

urlpatterns = [
    path('api/video_list/', VideoList.as_view(), name='video-list'),
    path('api/video_detail/<int:pk>/', VideoDetail.as_view(), name='video-detail'),
]