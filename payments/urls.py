from django.urls import path

from .views import (
    PaymentDetailView,
    PaymentMethodView,
    PricesListView,
    StripeWebhookView,
)

urlpatterns = [
    # path('api/video_list/', VideoList.as_view(), name='video-list'),
    # path('api/video_detail/', VideoDetail.as_view(), name='video-detail'),
    # path('api/video_detail/<int:pk>/', VideoDetail.as_view(), name='video-detail'),
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path(
        "api/get_product_prices/", PricesListView.as_view(), name="get_product_prices"
    ),
    path(
        "api/payment_method/<int:pk>/",
        PaymentMethodView.as_view(),
        name="payment_method",
    ),
    path(
        "api/create_subscription/<int:pk>/",
        PaymentDetailView.as_view(),
        name="create_subscription",
    ),
]
