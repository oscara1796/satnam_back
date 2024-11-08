from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.


class CustomUser(AbstractUser):
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=30, unique=True)
    stripe_customer_id = models.CharField(max_length=150, null=True)
    stripe_subscription_id = models.CharField(max_length=150, null=True)
    paypal_subscription_id = models.CharField(max_length=150, null=True)
    paypal_next_billing_time = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=False)
    paypal_failed_payments_count = models.IntegerField(default=0) 

    def __str__(self):
        return self.username


class TrialDays(models.Model):
    days = models.IntegerField(default=0)

    def __str__(self):
        return str(self.days)
