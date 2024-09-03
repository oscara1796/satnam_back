import json
import os

import requests
import stripe
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from dotenv import load_dotenv
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import TrialDays
from payments.models import SubscriptionPlan
from payments.paypal_functions import get_paypal_access_token

load_dotenv(".env.dev")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


class SubscriptionPlanAPITests(APITestCase):

    def setUp(self):
        # Create a staff user
        self.staff_user = get_user_model().objects.create_user(
            username="staff", email="staff@gmail.com", is_staff=True
        )
        self.client.force_authenticate(user=self.staff_user)

        # Create a non-staff user
        self.non_staff_user = get_user_model().objects.create_user(
            username="nonstaff", email="nonstaff@gmail.com", is_staff=False
        )

    def test_create_subscription_plan_with_trial_days(self):
        # Set up trial days
        TrialDays.objects.create(days=7)

        url = reverse("subscription_plan")
        image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
        with open(image_path, "rb") as image_file:
            data = {
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
            response = self.client.post(url, data, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify local database update
        plan = SubscriptionPlan.objects.get(name="Premium Plan with Trial")
        self.assertIsNotNone(plan)

        # Verify Stripe product creation
        stripe_product = stripe.Product.retrieve(plan.stripe_product_id)
        self.assertEqual(stripe_product.name, data["name"])

        # Verify Stripe price creation
        stripe_price = stripe.Price.retrieve(plan.stripe_price_id)
        self.assertEqual(
            stripe_price.unit_amount, 2000
        )  # Since Stripe stores amounts in cents

        # Verify PayPal Plan creation with trial days
        access_token = get_paypal_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        paypal_response = requests.get(
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{plan.paypal_plan_id}",
            headers=headers,
        )
        paypal_plan_details = paypal_response.json()
        self.assertEqual(paypal_plan_details["status"], "ACTIVE")
        self.assertEqual(paypal_plan_details["name"], data["name"])

        # Verify trial days in the billing cycles
        trial_cycle = next(
            (
                cycle
                for cycle in paypal_plan_details["billing_cycles"]
                if cycle["tenure_type"] == "TRIAL"
            ),
            None,
        )
        self.assertIsNotNone(trial_cycle)
        self.assertEqual(trial_cycle["total_cycles"], 7)

    def test_update_subscription_plan_as_staff(self):
        url = reverse("subscription_plan")
        image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
        with open(image_path, "rb") as image_file:
            data = {
                "name": "Premium Plan",
                "description": "A premium plan for advanced users.",
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
            response = self.client.post(url, data, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify local database update
        plan = SubscriptionPlan.objects.get(name="Premium Plan")
        self.assertIsNotNone(plan)

        # Endpoint and new data
        url = reverse("subscription_plan", kwargs={"pk": plan.pk})
        updated_data = {
            "name": "Updated Plan",
            "description": "An updated plan for advanced users.",
            "price": 40.00,
            "frequency_type": "year",
        }

        # Perform update operation
        response = self.client.put(url, updated_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify update in the database
        updated_plan = SubscriptionPlan.objects.get(pk=plan.pk)
        self.assertEqual(updated_plan.name, "Updated Plan")
        self.assertEqual(updated_plan.price, 40.00)
        self.assertEqual(updated_plan.frequency_type, "year")

        # Verify update in Stripe (assuming you have a function or mock to update Stripe details)
        stripe_product = stripe.Product.retrieve(updated_plan.stripe_product_id)
        self.assertEqual(stripe_product.name, updated_data["name"])

        stripe_price = stripe.Price.retrieve(updated_plan.stripe_price_id)
        self.assertEqual(
            stripe_price.unit_amount, 4000
        )  # Since Stripe stores amounts in cents
        self.assertEqual(
            stripe_price.recurring.interval, updated_data["frequency_type"]
        )

        # Verify update in PayPal (assuming functionality to check PayPal plan updates)
        access_token = get_paypal_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        paypal_response = requests.get(
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{updated_plan.paypal_plan_id}",
            headers=headers,
        )
        paypal_plan_details = paypal_response.json()
        self.assertEqual(paypal_plan_details["name"], updated_data["name"])
        self.assertEqual(paypal_plan_details["status"], "ACTIVE")

        # Verify the old plan is deactivated (if applicable)
        old_paypal_response = requests.get(
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{plan.paypal_plan_id}",
            headers=headers,
        )
        old_paypal_plan_details = old_paypal_response.json()
        self.assertEqual(old_paypal_plan_details["status"], "INACTIVE")

    def test_delete_subscription_plan_as_staff(self):
        url = reverse("subscription_plan")
        image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
        with open(image_path, "rb") as image_file:
            data = {
                "name": "Premium Plan",
                "description": "A premium plan for advanced users.",
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
            response = self.client.post(url, data, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify local database update
        plan = SubscriptionPlan.objects.get(name="Premium Plan")
        self.assertIsNotNone(plan)

        url = reverse("subscription_plan", kwargs={"pk": plan.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(SubscriptionPlan.objects.count(), 0)

        # Verify that Stripe product is deactivated
        try:
            stripe_product = stripe.Product.retrieve(plan.stripe_product_id)
            self.assertFalse(stripe_product.active)
        except stripe.error.StripeError as e:
            self.fail(f"Stripe product deletion failed: {str(e)}")

        # Verify PayPal plan deactivation
        access_token = get_paypal_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        paypal_url = (
            f"https://api-m.sandbox.paypal.com/v1/billing/plans/{plan.paypal_plan_id}"
        )
        paypal_response = requests.get(paypal_url, headers=headers)
        paypal_plan_details = paypal_response.json()
        self.assertEqual(paypal_plan_details["status"], "INACTIVE")

    def test_access_denied_for_non_staff(self):

        url = reverse("subscription_plan")
        image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
        with open(image_path, "rb") as image_file:
            data = {
                "name": "Premium Plan",
                "description": "A premium plan for advanced users.",
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
            response = self.client.post(url, data, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify local database update
        plan = SubscriptionPlan.objects.get(name="Premium Plan")
        self.assertIsNotNone(plan)

        self.client.force_authenticate(user=self.non_staff_user)
        url = reverse("subscription_plan")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = reverse("subscription_plan", kwargs={"pk": plan.pk})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.put(url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.staff_user)

        # Add more tests for POST, PUT, DELETE to ensure non-staff users cannot access these methods

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
