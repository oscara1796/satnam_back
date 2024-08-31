import json
import os

import requests
import stripe
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import TrialDays  # Replace with your actual import
from payments.models import SubscriptionPlan
from payments.paypal_functions import get_paypal_access_token

PASSWORD = "pAssw0rd!"


def create_user(
    username="testuser", password=PASSWORD, email="user@example.com", is_staff=False
):
    return get_user_model().objects.create_user(
        username=username, password=password, email=email, is_staff=is_staff
    )


class TrialDaysTests(APITestCase):

    def setUp(self):
        self.user = create_user("testuser", PASSWORD, "testuser@test.com")
        self.staff_user = create_user("staffuser", PASSWORD, "staffuser@test.com", True)

        # Log in as staff user
        response = self.client.post(
            reverse("log_in"),
            data={"username": self.staff_user.username, "password": PASSWORD},
        )
        self.access_token = response.data["access"]

        response = self.client.post(
            reverse("log_in"),
            data={"username": self.user.username, "password": PASSWORD},
        )
        self.non_staff_user_access_token = response.data["access"]

    def test_create_trial_day(self):
        url = reverse("trial_days")
        data = {"days": 30}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["days"], 30)

    def test_get_all_trial_days(self):
        TrialDays.objects.create(days=10)
        TrialDays.objects.create(days=20)

        url = reverse("trial_days")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_single_trial_day(self):
        trial_day = TrialDays.objects.create(days=15)
        url = reverse("trial_day_detail", kwargs={"pk": trial_day.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 15)

    def test_delete_trial_day(self):
        trial_day = TrialDays.objects.create(days=15)
        url = reverse("trial_day_detail", kwargs={"pk": trial_day.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TrialDays.objects.filter(pk=trial_day.id).exists())

    def test_non_staff_user_access(self):
        url = reverse("trial_days")
        data = {"days": 30}
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.non_staff_user_access_token}"
        )
        response = self.client.post(url, data, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        TrialDays.objects.create(days=10)
        TrialDays.objects.create(days=20)
        url = reverse("trial_days")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        trial_day = TrialDays.objects.create(days=15)
        url = reverse("trial_day_detail", kwargs={"pk": trial_day.id})
        response = self.client.delete(url)
        self.assertNotEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_trial_day_with_subscription_plan(self):
        # Create a subscription plan
        subscription_url = reverse("subscription_plan")
        image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
        with open(image_path, "rb") as image_file:
            subscription_data = {
                "name": "Premium Plan with Trial",
                "description": "A premium plan with trial days.",
                "image": SimpleUploadedFile(
                    name="test_image.png",
                    content=image_file.read(),
                    content_type="image/png",
                ),
                "features": json.dumps(
                    [
                        {"name": "Feature 1 Description"},
                        {"name": "Feature 2 Description"},
                    ]
                ),
                "metadata": json.dumps({"meta1": "data1"}),
                "frequency_type": "month",
                "price": 20.00,
            }
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
            response = self.client.post(
                subscription_url, subscription_data, format="multipart"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        subscription_plan = SubscriptionPlan.objects.get(name="Premium Plan with Trial")

        url = reverse("trial_days")
        data = {"days": 30}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["days"], 30)

        # Verify the trial days in the subscription plan model
        subscription_plan.refresh_from_db()

        # Verify the changes on PayPal
        access_token = get_paypal_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        paypal_response = requests.get(
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{subscription_plan.paypal_plan_id}",
            headers=headers,
        )
        paypal_plan_details = paypal_response.json()
        trial_cycle = next(
            (
                cycle
                for cycle in paypal_plan_details["billing_cycles"]
                if cycle["tenure_type"] == "TRIAL"
            ),
            None,
        )
        self.assertIsNotNone(trial_cycle)
        self.assertEqual(trial_cycle["total_cycles"], 30)

    def test_update_trial_day_with_subscription_plan(self):
        # Create a subscription plan
        subscription_url = reverse("subscription_plan")
        image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
        with open(image_path, "rb") as image_file:
            subscription_data = {
                "name": "Premium Plan with Trial",
                "description": "A premium plan with trial days.",
                "image": SimpleUploadedFile(
                    name="test_image.png",
                    content=image_file.read(),
                    content_type="image/png",
                ),
                "features": json.dumps(
                    [
                        {"name": "Feature 1 Description"},
                        {"name": "Feature 2 Description"},
                    ]
                ),
                "metadata": json.dumps({"meta1": "data1"}),
                "frequency_type": "month",
                "price": 20.00,
            }
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
            response = self.client.post(
                subscription_url, subscription_data, format="multipart"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        subscription_plan = SubscriptionPlan.objects.get(name="Premium Plan with Trial")

        trial_day = TrialDays.objects.create(days=15)
        url = reverse("trial_day_detail", kwargs={"pk": trial_day.id})
        data = {"days": 45}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 45)

        # Verify the trial days in the subscription plan model
        subscription_plan.refresh_from_db()

        # Verify the changes on PayPal
        access_token = get_paypal_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        paypal_response = requests.get(
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{subscription_plan.paypal_plan_id}",
            headers=headers,
        )
        paypal_plan_details = paypal_response.json()
        trial_cycle = next(
            (
                cycle
                for cycle in paypal_plan_details["billing_cycles"]
                if cycle["tenure_type"] == "TRIAL"
            ),
            None,
        )
        self.assertIsNotNone(trial_cycle)
        self.assertEqual(trial_cycle["total_cycles"], 45)

    def test_delete_trial_day_with_subscription_plan(self):
        # Create a subscription plan
        subscription_url = reverse("subscription_plan")
        image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
        with open(image_path, "rb") as image_file:
            subscription_data = {
                "name": "Premium Plan with Trial",
                "description": "A premium plan with trial days.",
                "image": SimpleUploadedFile(
                    name="test_image.png",
                    content=image_file.read(),
                    content_type="image/png",
                ),
                "features": json.dumps(
                    [
                        {"name": "Feature 1 Description"},
                        {"name": "Feature 2 Description"},
                    ]
                ),
                "metadata": json.dumps({"meta1": "data1"}),
                "frequency_type": "month",
                "price": 20.00,
            }
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
            response = self.client.post(
                subscription_url, subscription_data, format="multipart"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        subscription_plan = SubscriptionPlan.objects.get(name="Premium Plan with Trial")

        trial_day = TrialDays.objects.create(days=15)
        url = reverse("trial_day_detail", kwargs={"pk": trial_day.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TrialDays.objects.filter(pk=trial_day.id).exists())

        # Verify the trial days are set to zero in the subscription plan model
        subscription_plan.refresh_from_db()

        # Verify the changes on PayPal
        access_token = get_paypal_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        paypal_response = requests.get(
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{subscription_plan.paypal_plan_id}",
            headers=headers,
        )
        paypal_plan_details = paypal_response.json()
        trial_cycle = next(
            (
                cycle
                for cycle in paypal_plan_details["billing_cycles"]
                if cycle["tenure_type"] == "TRIAL"
            ),
            None,
        )
        self.assertIsNone(trial_cycle)

    def deactivate_paypal_plan(self, plan_id):
        """Send a request to PayPal to deactivate a billing plan."""
        access_token = (
            get_paypal_access_token()
        )  # Ensure this method retrieves a valid access token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        paypal_url = (
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{plan_id}/deactivate"
        )
        response = requests.post(paypal_url, headers=headers)
        if response.status_code not in (200, 204):
            raise Exception(
                f"Failed to deactivate PayPal plan {plan_id}: {response.text}"
            )

    def tearDown(self):
        # Cleanup Stripe and PayPal resources if necessary
        plans = SubscriptionPlan.objects.all()
        for plan in plans:
            try:
                stripe.Product.modify(plan.stripe_product_id, active=False)
                print(f"Successfully deleted Stripe product {plan.stripe_product_id}")
            except stripe.error.StripeError as e:
                print(f"Failed to delete Stripe product {plan.stripe_product_id}: {e}")

            # Deactivate PayPal plan if applicable
            if plan.paypal_plan_id:
                self.deactivate_paypal_plan(plan.paypal_plan_id)

            # Clean up database
            plan.delete()
        get_user_model().objects.all().delete()
