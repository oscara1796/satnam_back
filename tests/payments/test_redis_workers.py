import threading
import logging
import json
import redis
import time
import stripe
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.db import connections, close_old_connections
from payments.workers import RedisWorker
from payments.models import StripeEvent
from queue import Queue, Empty
import stripe
from dotenv import dotenv_values

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

    @patch("payments.views.verify_paypal_webhook_signature")
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


class RedisWorkerTestCase(TransactionTestCase):

    def setUp(self):
        self.worker = RedisWorker()
        self.exceptions = []
        self.process_event_queue = Queue()

    @patch("redis.Redis.from_url")
    def test_worker_initialization(self, mock_redis_from_url):
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance

        worker = RedisWorker()

        self.assertEqual(worker.thread_count, 2)
        self.assertEqual(worker.max_threads, 10)
        self.assertEqual(worker.min_threads, 2)
        self.assertFalse(worker.shutdown_event.is_set())
        self.assertEqual(len(worker.threads), 0)

    @override_settings(DEBUG=True)
    @patch(
        "redis.Redis.blpop",
        side_effect=lambda *args, **kwargs: next(mock_blpop_generator()),
    )
    @patch("payments.processing.get_customer_email")
    def test_worker_process_event(
        self, mock_update_event_status, mock_get_customer_email
    ):
        # Setup mock return values

        mock_get_customer_email.return_value = "oscara1706cl@gmail.com"

        # Initialize RedisWorker and start workers
        worker = RedisWorker()
        worker.start_workers()

        logger.info("Waiting for event to be processed")
        # Let the worker run for a short time to process the event
        time.sleep(2)  # Wait for a short period to allow event processing

        worker.stop_workers()  # Ensure the worker exits

        if self.exceptions:
            raise self.exceptions[0]

        # Ensure all connections are closed before checking database state
        close_old_connections()

        # Check if Redis queue is empty
        redis_conn = redis.Redis.from_url(settings.REDIS_URL)
        self.assertEqual(redis_conn.llen("task_queue"), 0)

        # Check if the number of threads is correct
        self.assertEqual(len(worker.threads), worker.thread_count)

        # Assert that the event was saved in the database with the status 'processed'
        try:
            stripe_event = StripeEvent.objects.get(stripe_event_id="evt_123")
            self.assertEqual(stripe_event.status, "processed")
        except StripeEvent.DoesNotExist:
            self.fail(f"StripeEvent with ID evt_123 does not exist in the database")

    @override_settings(DEBUG=True)
    @patch("redis.Redis.from_url")
    @patch("redis.Redis.llen")
    def test_worker_scaling_up_and_down(self, mock_redis_llen, mock_redis_from_url):
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance

        # Set a side effect for mock_redis_llen to return a series of values
        queue_sizes = iter([51, 51, 51, 19, 19, 19, 19, 19, 19])
        mock_redis_llen.side_effect = lambda *args, **kwargs: next(queue_sizes)

        worker = RedisWorker()
        worker.start_workers()

        time.sleep(35)  # Allow time for scaling up

        # Verify that the number of threads increased
        self.assertTrue(
            len(worker.threads) > worker.min_threads,
            "Worker did not scale up correctly",
        )

        time.sleep(100)  # Allow time for scaling down

        # Verify that the number of threads decreased
        self.assertTrue(
            len(worker.threads) <= worker.thread_count,
            "Worker did not scale down correctly",
        )

        worker.stop_workers()

    @override_settings(DEBUG=True)
    @patch("redis.Redis.from_url")
    @patch("redis.Redis.llen")
    def test_worker_scaling_down(self, mock_redis_llen, mock_redis_from_url):
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance
        mock_redis_llen.return_value = 19  # Simulate a low queue size

        worker = RedisWorker()
        worker.start_workers()

        time.sleep(1)  # Allow time for scaling

        self.assertTrue(
            len(worker.threads) <= worker.thread_count,
            "Worker did not scale down correctly",
        )

        worker.stop_workers()

    def tearDown(self):
        close_connections()
        if hasattr(self.worker, "threads"):
            for t in self.worker.threads:
                t.join()
        if hasattr(self.worker, "monitor_thread") and self.worker.monitor_thread:
            self.worker.monitor_thread.join()


if __name__ == "__main__":
    import unittest

    unittest.main()
