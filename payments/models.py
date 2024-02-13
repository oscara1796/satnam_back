from django.db import models

# Create your models here.


class StripeEvent(models.Model):
    stripe_event_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20)
