from django.urls import path 
from .views import VideoList, VideoDetail, CategoryAPIView, LinkCategoryVideoAPIView

urlpatterns = [
    path('api/video_list/', VideoList.as_view(), name='video-list'),
    path('api/video_detail/', VideoDetail.as_view(), name='video-detail'),
    path('api/category_list/', CategoryAPIView.as_view(), name='category-list'),
    path('api/category_detail/', CategoryAPIView.as_view(), name='category-detail'),
    path('api/category_detail/<int:pk>/', CategoryAPIView.as_view(), name='category-detail'),
    path('api/video_detail/<int:pk>/', VideoDetail.as_view(), name='video-detail'),
    path('categories/<int:category_id>/videos/<int:video_id>/link/', LinkCategoryVideoAPIView.as_view(), name='link-category-video'),
]
