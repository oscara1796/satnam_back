from django.db import models

# Create your models here.


class StripeEvent(models.Model):
    stripe_event_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20)




class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    image = models.URLField(null=True, blank=True)
    features = models.JSONField()
    metadata = models.JSONField()
    paypal_plan_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_product_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_price_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

