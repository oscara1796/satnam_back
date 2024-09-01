import json
import logging
from queue import Queue
from unittest.mock import MagicMock, patch

import redis
import stripe
from django.conf import settings
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from dotenv import dotenv_values
from rest_framework.test import APIClient

from payments.models import StripeEvent

env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]


logger = logging.getLogger("django")


def close_connections():
    for conn in connections.all():
        conn.close()


def mock_blpop_generator():
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
    while True:
        yield ("task_queue", payload_json)


class PayPalWebhookTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("paypal_webhook")  # Ensure the URL name matches your urls.py

    @patch("payments.paypal_functions.verify_paypal_webhook_signature")
    @patch("redis.Redis.from_url")
    def test_paypal_webhook_success(self, mock_redis_from_url, mock_verify_signature):
        # Configure mock objects
        mock_verify_signature.return_value = True
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance

        # Use the provided payload
        event = {
            "id": "WH-4JX204663A8287931-6LX68303T63222804",
            "event_version": "1.0",
            "create_time": "2024-08-20T04:50:03.566Z",
            "resource_type": "subscription",
            "resource_version": "2.0",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "summary": "Subscription activated",
            "resource": {
                "quantity": "1",
                "subscriber": {
                    "email_address": "oscar.carrillo2941@alumnos.udg.mx",
                    "payer_id": "UEPZTTKJQQ8JC",
                    "name": {"given_name": "John", "surname": "Doe"},
                    "shipping_address": {
                        "address": {
                            "address_line_1": "1 Main St",
                            "admin_area_2": "San Jose",
                            "admin_area_1": "CA",
                            "postal_code": "95131",
                            "country_code": "US",
                        }
                    },
                },
                "create_time": "2024-08-20T04:49:31Z",
                "plan_overridden": False,
                "shipping_amount": {"currency_code": "MXN", "value": "0.0"},
                "start_time": "2024-08-20T04:48:43Z",
                "update_time": "2024-08-20T04:49:32Z",
                "billing_info": {
                    "outstanding_balance": {"currency_code": "MXN", "value": "0.0"},
                    "cycle_executions": [
                        {
                            "tenure_type": "REGULAR",
                            "sequence": 1,
                            "cycles_completed": 1,
                            "cycles_remaining": 0,
                            "current_pricing_scheme_version": 1,
                            "total_cycles": 0,
                        }
                    ],
                    "last_payment": {
                        "amount": {"currency_code": "MXN", "value": "250.0"},
                        "time": "2024-08-20T04:49:31Z",
                    },
                    "next_billing_time": "2024-09-19T10:00:00Z",
                    "failed_payments_count": 0,
                },
                "links": [
                    {
                        "href": "https://api.sandbox.paypal.com/v1/billing/subscriptions/I-2C054R2S7S33/cancel",
                        "rel": "cancel",
                        "method": "POST",
                        "encType": "application/json",
                    },
                    {
                        "href": "https://api.sandbox.paypal.com/v1/billing/subscriptions/I-2C054R2S7S33",
                        "rel": "edit",
                        "method": "PATCH",
                        "encType": "application/json",
                    },
                    {
                        "href": "https://api.sandbox.paypal.com/v1/billing/subscriptions/I-2C054R2S7S33",
                        "rel": "self",
                        "method": "GET",
                        "encType": "application/json",
                    },
                    {
                        "href": "https://api.sandbox.paypal.com/v1/billing/subscriptions/I-2C054R2S7S33/suspend",
                        "rel": "suspend",
                        "method": "POST",
                        "encType": "application/json",
                    },
                    {
                        "href": "https://api.sandbox.paypal.com/v1/billing/subscriptions/I-2C054R2S7S33/capture",
                        "rel": "capture",
                        "method": "POST",
                        "encType": "application/json",
                    },
                ],
                "id": "I-2C054R2S7S33",
                "plan_id": "P-5G929033T98692209M3CB6EI",
                "status": "ACTIVE",
                "status_update_time": "2024-08-20T04:49:32Z",
            },
            "links": [
                {
                    "href": "https://api.sandbox.paypal.com/v1/notifications/webhooks-events/WH-4JX204663A8287931-6LX68303T63222804",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": "https://api.sandbox.paypal.com/v1/notifications/webhooks-events/WH-4JX204663A8287931-6LX68303T63222804/resend",
                    "rel": "resend",
                    "method": "POST",
                },
            ],
        }
        payload_json = json.dumps(event)

        # Perform POST request
        response = self.client.post(
            self.url, data=payload_json, content_type="application/json"
        )

        # Verify the response
        self.assertEqual(response.status_code, 200)
        mock_redis_instance.rpush.assert_called_once_with("task_queue", payload_json)
        mock_verify_signature.assert_called_once()

    @patch("payments.paypal_functions.verify_paypal_webhook_signature")
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

    def tearDown(self):
        # Any cleanup if necessary
        close_connections()


class StripeWebhookViewTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("stripe-webhook")  # Adjust the URL name as necessary

    @patch("stripe.Event.construct_from")
    @patch("redis.Redis.from_url")
    def test_stripe_webhook(
        self, mock_redis_from_url, mock_stripe_event_construct_from
    ):
        # Setup the mock Redis instance
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance

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
        mock_event.data.object.id = "in_123"
        mock_event.data.object.amount_due = 2000
        mock_event.data.object.currency = "usd"
        mock_event.data.object.customer = "cus_123"
        mock_stripe_event_construct_from.return_value = mock_event

        response = self.client.post(
            self.url, data=payload_json, content_type="application/json"
        )

        # Check response status
        self.assertEqual(response.status_code, 200)

        # Check if event was added to Redis queue
        mock_redis_instance.rpush.assert_called_with("task_queue", payload_json)

        # Check if stripe.Event.construct_from was called with the correct payload
        mock_stripe_event_construct_from.assert_called_with(payload, stripe.api_key)

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



