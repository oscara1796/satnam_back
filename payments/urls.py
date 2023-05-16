from django.urls import path 
from .views import  PaymentDetailView, SubscriptionDetailView, PricesListView

urlpatterns = [
    # path('api/video_list/', VideoList.as_view(), name='video-list'),
    # path('api/video_detail/', VideoDetail.as_view(), name='video-detail'),
    # path('api/video_detail/<int:pk>/', VideoDetail.as_view(), name='video-detail'),
    path('api/get_product_prices/', PricesListView.as_view(), name='get_product_prices'),
    path('api/create_payment_method/<int:pk>/', PaymentDetailView.as_view(), name='create_payment_method'),
    path('api/create_subscription/<int:pk>/', SubscriptionDetailView.as_view(), name='create_subscription'),
]