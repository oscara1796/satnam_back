import json
from datetime import datetime

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from dotenv import dotenv_values
from rest_framework.test import APITestCase

# Load the environment variables from .env.dev file
env_vars = dotenv_values(".env.dev")
PASSWORD = "pAssw0rd!"


class StripeIntegrationTest(APITestCase):

    def setUp(self):
        # Initialize the Stripe API client with your API key
        stripe.api_key = env_vars["STRIPE_SECRET_KEY"]
        # self.subscription_url = reverse('subscription')
        response = self.client.post(
            reverse("sign_up"),
            data={
                "username": "testuser",
                "email": "user@example.com",
                "first_name": "Test",
                "last_name": "User",
                "telephone": "3331722789",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        # Retrieve the user object from the database
        self.user = get_user_model().objects.last()
        response = self.client.post(
            reverse("log_in"),
            data={
                "username": self.user.username,
                "password": PASSWORD,
            },
        )
        self.access = response.data["access"]

    def tearDown(self):
        # Clean up code
        # Delete test data, reset state, etc.
        url = reverse("user-detail", args=[self.user.id])
        self.client.delete(url, HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def test_create_subscription(self):
        # Make the API request

        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
            "price_id": settings.STRIPE_SUBSCRIPTION_PRICE_ID,
        }

        url = reverse("create_subscription", args=[self.user.id])
        response = self.client.post(
            url, card_data, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 201)

        self.assertIn("stripe_customer_id", response.data)
        self.assertIn("subscription_id", response.data)
        self.assertIn("status", response.data)
        user = get_user_model().objects.get(id=self.user.id)
        self.assertTrue(user.active)
        # self.assertTrue(stripe.PaymentMethod.retrieve(response_obj["id"]))
        subscription_id = response.data["subscription_id"]
        self.assertIsNotNone(subscription_id)

    def test_create_subscription_with_payment_method(self):
        # Make the API request

        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
        }

        url = reverse("payment_method", kwargs={"pk": self.user.pk})

        response = self.client.post(
            url, card_data, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 201)

        # Verify the payment method ID is returned in the response
        self.assertIn("payment_method_id", response.data)
        created_payment_method_id = response.data["payment_method_id"]

        card_data = {
            "payment_method_id": created_payment_method_id,
            "price_id": settings.STRIPE_SUBSCRIPTION_PRICE_ID,
        }

        url = reverse("create_subscription", args=[self.user.id])
        response = self.client.post(
            url, card_data, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 201)

        self.assertIn("stripe_customer_id", response.data)
        self.assertIn("subscription_id", response.data)
        self.assertIn("status", response.data)
        user = get_user_model().objects.get(id=self.user.id)
        self.assertTrue(user.active)
        # self.assertTrue(stripe.PaymentMethod.retrieve(response_obj["id"]))
        subscription_id = response.data["subscription_id"]
        self.assertIsNotNone(subscription_id)

    def test_create_subscription_without_price_Error(self):
        # Make the API request

        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
        }

        url = reverse("create_subscription", args=[self.user.id])
        response = self.client.post(
            url, card_data, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_get_product_prices(self):
        url = reverse("get_product_prices")
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        print(response.data)
        response_obj = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        for product in response_obj:
            # print(product)
            self.assertTrue(product["id"].startswith("prod_"))
            self.assertIsNotNone(product["name"])

    def test_delete_subscription(self):
        # Card data remains the same
        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
            "price_id": settings.STRIPE_SUBSCRIPTION_PRICE_ID,
        }

        # Creating the subscription
        url = reverse("create_subscription", args=[self.user.id])
        response = self.client.post(
            url, card_data, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        user = get_user_model().objects.get(id=self.user.id)
        self.assertTrue(user.active)
        self.assertEqual(response.status_code, 201)

        # Deleting (actually updating) the subscription
        response = self.client.delete(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data, {"success": "Subscription set to cancel at period end"}
        )

        # Retrieve the subscription from Stripe to verify it's set to cancel at period end
        subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
        self.assertTrue(subscription.cancel_at_period_end)

    def test_get_subscription(self):
        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
            "price_id": settings.STRIPE_SUBSCRIPTION_PRICE_ID,
        }

        url = reverse("create_subscription", args=[self.user.id])
        response = self.client.post(
            url, card_data, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(id=self.user.id)
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subscription_id"], user.stripe_subscription_id)
        self.assertIn("status", response.data)
        self.assertIn("current_period_end", response.data)
        self.assertIn("cancel_at_period_end", response.data)

    def test_create_subscription_with_trial(self):
        # Add trial period data
        trial_period_days = 14  # for example, a 14-day trial

        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
            "price_id": settings.STRIPE_SUBSCRIPTION_PRICE_ID,
            "trial": trial_period_days,  # Add trial period to the request data
        }

        url = reverse("create_subscription", args=[self.user.id])
        response = self.client.post(
            url, card_data, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("status", response.data)
        self.assertEqual(response.data["status"], "trialing")
        self.assertTrue(response.data["user_is_active"])
        user = get_user_model().objects.get(id=self.user.id)
        self.assertTrue(user.active)
        self.assertEqual(response.data["subscription_id"], user.stripe_subscription_id)
        trial_end = response.data["trial_end"]
        trial_start = response.data["trial_start"]

        # Convert Unix timestamps to datetime objects
        end_date = datetime.fromtimestamp(trial_end)
        start_date = datetime.fromtimestamp(trial_start)

        # Calculate the difference in days
        difference_in_days = (end_date - start_date).days
        self.assertEqual(difference_in_days, trial_period_days)

    def test_patch_reactivate_subscription(self):
        # Card data remains the same
        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
            "price_id": settings.STRIPE_SUBSCRIPTION_PRICE_ID,
        }

        # Creating the subscription
        url = reverse("create_subscription", args=[self.user.id])
        response = self.client.post(
            url, card_data, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        user = get_user_model().objects.get(id=self.user.id)
        self.assertTrue(user.active)
        self.assertEqual(response.status_code, 201)

        # Deleting (actually updating) the subscription
        response = self.client.delete(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data, {"success": "Subscription set to cancel at period end"}
        )

        subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
        self.assertTrue(subscription.cancel_at_period_end)

        response = self.client.patch(
            url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["cancel_at_period_end"])

        subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
        self.assertFalse(subscription.cancel_at_period_end)

        # Retrieve the subscription from Stripe to verify it's set to cancel at period end


class PaymentMethodViewTests(APITestCase):

    def setUp(self):
        # Initialize the Stripe API client with your API key
        stripe.api_key = env_vars["STRIPE_SECRET_KEY"]
        # self.subscription_url = reverse('subscription')
        response = self.client.post(
            reverse("sign_up"),
            data={
                "username": "testuser2",
                "email": "user2@example.com",
                "first_name": "Test delete",
                "last_name": "User",
                "telephone": "3331722789",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        # Retrieve the user object from the database
        self.user = get_user_model().objects.last()
        response = self.client.post(
            reverse("log_in"),
            data={
                "username": self.user.username,
                "password": PASSWORD,
            },
        )
        self.access = response.data["access"]

        self.url = reverse("payment_method", kwargs={"pk": self.user.pk})

    def test_post_payment_method(self):
        # Test for creating a new payment method for the user
        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
        }

        # Send a POST request to create a new payment method
        response = self.client.post(
            self.url,
            card_data,
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        # Verify the payment method ID is returned in the response
        self.assertIn("payment_method_id", response.data)
        created_payment_method_id = response.data["payment_method_id"]

        # Retrieve all payment methods for the user and verify the created one is listed
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertIsNotNone(response.data["default_payment_method"])
        self.assertEqual(
            response.data["default_payment_method"].get("id"), created_payment_method_id
        )
        self.assertEqual(response.status_code, 200)
        all_payment_methods = response.data["all_payment_methods"]
        self.assertIn(
            created_payment_method_id, [pm["id"] for pm in all_payment_methods]
        )

    def test_put_update_default_payment_method(self):
        # Test setup: Create a new Visa card payment method
        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
        }

        # Send a POST request to create a new payment method and verify success
        response = self.client.post(
            self.url,
            card_data,
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("payment_method_id", response.data)

        # Store the payment method ID for later verification
        visa_payment_method_id = response.data

        # Send a PUT request to update the default payment method to the newly created Visa card
        response = self.client.put(
            self.url,
            {"payment_method_id": visa_payment_method_id["payment_method_id"]},
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        # Retrieve and verify the updated default payment method
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)

        # Extract and verify the default payment method ID
        default_payment_method_id = response.data["default_payment_method"]
        if isinstance(default_payment_method_id, dict):
            default_payment_method_id = default_payment_method_id.get("id")
        self.assertEqual(
            default_payment_method_id, visa_payment_method_id["payment_method_id"]
        )

        # Test setup: Create a new MasterCard payment method
        card_data = {
            "number": "5555555555554444",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
        }

        # Send a POST request to create a new payment method and verify success
        response = self.client.post(
            self.url,
            card_data,
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("payment_method_id", response.data)

        # Store the payment method ID for later verification
        mc_payment_method_id = response.data

        # Send a PUT request to update the default payment method to the newly created MasterCard
        response = self.client.put(
            self.url,
            {"payment_method_id": mc_payment_method_id["payment_method_id"]},
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        # Retrieve and verify the updated default payment method
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)

        # Extract and verify the default payment method ID
        default_payment_method_id = response.data["default_payment_method"]
        if isinstance(default_payment_method_id, dict):
            default_payment_method_id = default_payment_method_id.get("id")
        self.assertEqual(
            default_payment_method_id, mc_payment_method_id["payment_method_id"]
        )

    def test_get_payment_methods(self):

        payment_ids = []

        number_of_payment_methods = 3

        for i in range(number_of_payment_methods):

            card_data = {
                "number": "4242424242424242",
                "exp_month": 12,
                "exp_year": 2024,
                "cvc": "123",
            }
            response = self.client.post(
                self.url,
                card_data,
                HTTP_AUTHORIZATION=f"Bearer {self.access}",
                format="json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertIn("payment_method_id", response.data)
            payment_ids.append(response.data)

        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.data
        # Verify 'default_payment_method' is not None
        self.assertIsNotNone(data["default_payment_method"])

        # Verify 'all_payment_methods' is a list
        self.assertIsInstance(data["all_payment_methods"], list)

        # Verify the number of payment methods
        self.assertEqual(len(data["all_payment_methods"]), number_of_payment_methods)

        for payment_method in data["all_payment_methods"]:
            # Verify that it is a PaymentMethod object (or however you expect it to be structured)
            self.assertIn("id", payment_method)
            self.assertIn("billing_details", payment_method)
            self.assertIn("card", payment_method)
            self.assertIn("created", payment_method)
            self.assertIn("customer", payment_method)
            self.assertIn("livemode", payment_method)
            self.assertIn("metadata", payment_method)
            self.assertIn("object", payment_method)
            self.assertIn("type", payment_method)
            self.assertEqual(payment_method["object"], "payment_method")
            self.assertEqual(payment_method["type"], "card")

            # Add more detailed checks as necessary, e.g., for 'card' details
            card = payment_method["card"]
            self.assertIn("brand", card)
            self.assertIn("exp_month", card)
            self.assertIn("exp_year", card)
            self.assertIn("last4", card)
            self.assertEqual(card["brand"], "visa")
            self.assertEqual(card["exp_month"], 12)
            self.assertEqual(card["exp_year"], 2024)
            self.assertEqual(card["last4"], "4242")

        default_payment_method_id = payment_ids[0].get("payment_method_id")
        response = self.client.put(
            self.url,
            {"payment_method_id": default_payment_method_id},
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)

        # Verify the default payment method has been updated
        data = response.data
        self.assertEqual(
            data["default_payment_method"].get("id"), default_payment_method_id
        )
        # Verify the response contains the expected keys
        # Note: This assumes you have set up test payment methods in Stripe

        # Verify the response contains the new payment method ID

    def test_delete_payment_method(self):

        card_data = {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2024,
            "cvc": "123",
        }

        # Send a POST request to create a new payment method and verify success
        response = self.client.post(
            self.url,
            card_data,
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("payment_method_id", response.data)

        default_payment_method_id = response.data["payment_method_id"]
        response = self.client.put(
            self.url,
            {"payment_method_id": default_payment_method_id},
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)

        # Verify the default payment method has been updated
        data = response.data
        self.assertEqual(
            data["default_payment_method"].get("id"), default_payment_method_id
        )

        # Assume 'pm_test_delete' is a valid payment method ID in your Stripe test account
        response = self.client.delete(
            self.url,
            {"payment_method_id": default_payment_method_id},
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {self.access}", format="json"
        )
        self.assertEqual(response.status_code, 200)

        # Verify the default payment method has been updated
        data = response.data

        self.assertIsNone(
            data["default_payment_method"]
        )  # Verify the default payment method is None
        self.assertIsInstance(
            data["all_payment_methods"], list
        )  # Verify all_payment_methods is a list
        self.assertEqual(len(data["all_payment_methods"]), 0)
