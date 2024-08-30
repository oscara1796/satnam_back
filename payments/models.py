from django.db import models
from django.conf import settings
import os
import boto3
import logging

# Create your models here.

logger = logging.getLogger("django")


class StripeEvent(models.Model):
    stripe_event_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20)


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(null=True, blank=True)
    features = models.JSONField()
    metadata = models.JSONField()
    frequency_type = models.CharField(max_length=10)
    price = models.DecimalField(max_digits=21, decimal_places=2)
    paypal_plan_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_product_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_price_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        # Delete associated image file
        if self.image:
            # Delete image from S3
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            try:
                s3.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=self.image.name
                )
            except Exception as e:
                logger.error(f"Error deleting image from S3: {e}")

        super(SubscriptionPlan, self).delete(*args, **kwargs)
