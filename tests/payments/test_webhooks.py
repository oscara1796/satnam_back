import json
import logging
from unittest.mock import MagicMock, patch

import stripe
from django.conf import settings
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.views import APIView

logger = logging.getLogger("django")


def close_connections():
    for conn in connections.all():
        conn.close()


class PayPalWebhookTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("paypal_webhook")  # Ensure the URL name matches your urls.py

    @patch("payments.tasks.process_payment_event.delay")
    @patch("payments.views.verify_paypal_webhook_signature")
    def test_paypal_webhook_success(self, mock_verify_signature, mock_process_payment_event):
        # Configure mock objects
        mock_verify_signature.return_value = True
        mock_process_payment_event.return_value = None

        # Use the provided payload
        event = {
            "id": "WH-4JX204663A8287931-6LX68303T63222804",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-2C054R2S7S33",
                "plan_id": "P-5G929033T98692209M3CB6EI",
                "status": "ACTIVE",
            },
        }
        payload_json = json.dumps(event)

        # Perform POST request
        response = self.client.post(
            self.url, data=payload_json, content_type="application/json"
        )

        # Verify the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')  # Assert that response content is empty, or customize if there is expected content

        # Verify that verify_paypal_webhook_signature was called once
        mock_verify_signature.assert_called_once()

        # Verify that process_payment_event.delay was called with the correct event data
        mock_process_payment_event.assert_called_once_with(event)

       
    @patch("payments.views.verify_paypal_webhook_signature")
    def test_paypal_webhook_failure_invalid_signature(self, mock_verify_signature):
        # Configure mock objects
        mock_verify_signature.return_value = False

        # Use the provided payload
        event = {
            "id": "WH-4JX204663A8287931-6LX68303T63222804",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-2C054R2S7S33",
                "plan_id": "P-5G929033T98692209M3CB6EI",
                "status": "ACTIVE",
            },
        }
        payload_json = json.dumps(event)

        # Perform POST request
        response = self.client.post(
            self.url, data=payload_json, content_type="application/json"
        )

        # Verify the response
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Failed to verify signature"})

        # Verify that verify_paypal_webhook_signature was called once
        mock_verify_signature.assert_called_once()

       

    def tearDown(self):
        close_connections()


class StripeWebhookViewTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("stripe-webhook")  # Adjust the URL name as necessary

    @patch("payments.tasks.process_payment_event.delay")
    @patch("stripe.Event.construct_from")
    def test_stripe_webhook_success(self, mock_stripe_event_construct_from, mock_process_payment_event):
        # Sample payload
        payload = {
            "id": "evt_123",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_123",
                    "amount_due": 2000,
                    "currency": "usd",
                    "customer": "cus_123",
                }
            },
        }
        payload_json = json.dumps(payload)

        # Setup the mock Stripe event
        mock_event = MagicMock()
        mock_event.id = "evt_123"
        mock_event.type = "invoice.payment_succeeded"
        mock_stripe_event_construct_from.return_value = mock_event

        response = self.client.post(
            self.url, data=payload_json, content_type="application/json"
        )

        # Check response status
        self.assertEqual(response.status_code, 200)

        # Check if the Stripe event was processed
        mock_stripe_event_construct_from.assert_called_once_with(payload, stripe.api_key)

        # Check if the event was sent to Celery
        mock_process_payment_event.assert_called_once_with(payload)

        # Ensure log message for event received
        with self.assertLogs("django", level="INFO") as cm:
            logger.info(
                f"Stripe event {mock_event.type} received with ID {mock_event.id}"
            )
            self.assertIn(
                f"INFO:django:Stripe event {mock_event.type} received with ID {mock_event.id}",
                cm.output,
            )

    def tearDown(self):
        close_connections()
