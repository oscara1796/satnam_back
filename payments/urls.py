from django.urls import path

from .views import (
    PaymentDetailView,
    PaymentMethodView,
    PricesListView,
    StripeWebhookView,
    SubscriptionPlanAPIView,
    PaypalSubscriptionView,
    paypal_webhook,
)

urlpatterns = [
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("paypal/webhook/", paypal_webhook, name="paypal_webhook"),
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
    path(
        "api/subscription_plan/",
        SubscriptionPlanAPIView.as_view(),
        name="subscription_plan",
    ),
    path(
        "api/subscription_plan_paypal/",
        PaypalSubscriptionView.as_view(),
        name="subscription_plan_paypal",
    ),
    path(
        "api/subscription_plan_paypal/<int:pk>/",
        PaypalSubscriptionView.as_view(),
        name="subscription_plan_paypal",
    ),
    path(
        "api/subscription_plan/<int:pk>/",
        SubscriptionPlanAPIView.as_view(),
        name="subscription_plan",
    ),
]
