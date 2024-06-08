import threading
import logging
import json
import redis
import time
import stripe
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from django.test import TransactionTestCase
from django.urls import reverse
from django.conf import settings
from django.db import connections, close_old_connections
from payments.workers import RedisWorker
from payments.models import StripeEvent
from queue import Queue, Empty

logger = logging.getLogger('django')

def close_connections():
    for conn in connections.all():
        conn.close()

def mock_blpop_generator():
    payload = {
        'id': 'evt_123',
        'type': 'invoice.payment_succeeded',
        'data': {'object': {
            'id': 'in_123',
            'amount_due': 2000,
            'currency': 'usd',
            'customer': 'cus_123'
        }}
    }
    payload_json = json.dumps(payload)
    while True:
        yield ('task_queue', payload_json)

class StripeWebhookViewTestCase(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('stripe-webhook')  # Adjust the URL name as necessary

    @patch('stripe.Event.construct_from')
    @patch('redis.Redis.from_url')
    def test_stripe_webhook(self, mock_redis_from_url, mock_stripe_event_construct_from):
        # Setup the mock Redis instance
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance

        # Sample payload
        payload = {
            'id': 'evt_123',
            'type': 'invoice.payment_succeeded',
            'data': {'object': {
                'id': 'in_123',
                'amount_due': 2000,
                'currency': 'usd',
                'customer': 'cus_123'
            }}
        }
        payload_json = json.dumps(payload)

        # Setup the mock Stripe event
        mock_event = MagicMock()
        mock_event.id = 'evt_123'
        mock_event.type = 'invoice.payment_succeeded'
        mock_event.data.object.id = 'in_123'
        mock_event.data.object.amount_due = 2000
        mock_event.data.object.currency = 'usd'
        mock_event.data.object.customer = 'cus_123'
        mock_stripe_event_construct_from.return_value = mock_event

        response = self.client.post(self.url, data=payload_json, content_type='application/json')

        # Check response status
        self.assertEqual(response.status_code, 200)

        # Check if event was added to Redis queue
        mock_redis_instance.rpush.assert_called_with('task_queue', payload_json)

        # Check if stripe.Event.construct_from was called with the correct payload
        mock_stripe_event_construct_from.assert_called_with(payload, stripe.api_key)

        # Ensure log message for event received
        with self.assertLogs('django', level='INFO') as cm:
            logger.info(f"Stripe event {mock_event.type} received with ID {mock_event.id}")
            self.assertIn(f"INFO:django:Stripe event {mock_event.type} received with ID {mock_event.id}", cm.output)

    def tearDown(self):
        close_connections()

class RedisWorkerTestCase(TransactionTestCase):

    def setUp(self):
        self.worker = RedisWorker()
        self.exceptions = []
        self.process_event_queue = Queue()

    @patch('redis.Redis.from_url')
    def test_worker_initialization(self, mock_redis_from_url):
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance

        worker = RedisWorker()

        self.assertEqual(worker.thread_count, 2)
        self.assertEqual(worker.max_threads, 10)
        self.assertEqual(worker.min_threads, 2)
        self.assertFalse(worker.shutdown_event.is_set())
        self.assertEqual(len(worker.threads), 0)

    @patch('redis.Redis.blpop', side_effect=lambda *args, **kwargs: next(mock_blpop_generator()))
    @patch('stripe.Event.construct_from')
    @patch('payments.processing.get_customer_email')
    @patch.object(RedisWorker, 'update_event_status')
    def test_worker_process_event(self, mock_update_event_status, mock_get_customer_email, mock_stripe_event_construct_from, mock_redis_blpop):
        # Setup mock return values
        mock_event = MagicMock()
        mock_event.id = 'evt_123'
        mock_event.type = 'invoice.payment_succeeded'
        mock_event.data.object.id = 'in_123'
        mock_event.data.object.amount_due = 2000
        mock_event.data.object.currency = 'usd'
        mock_event.data.object.customer = 'cus_123'
        mock_stripe_event_construct_from.return_value = mock_event
        mock_get_customer_email.return_value = 'oscara1706cl@gmail.com'

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

        # Check if the update_event_status was called with the correct parameters
        mock_update_event_status.assert_called_with(mock_event.id, 'processed')

        # Check if Redis queue is empty
        redis_conn = redis.Redis.from_url(settings.REDIS_URL)
        self.assertEqual(redis_conn.llen('task_queue'), 0)

        # Check if the number of threads is correct
        self.assertEqual(len(worker.threads), worker.thread_count)

    @patch('redis.Redis.from_url')
    @patch('redis.Redis.llen')
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
        self.assertTrue(len(worker.threads) > worker.min_threads, "Worker did not scale up correctly")

        time.sleep(90)  # Allow time for scaling down

        # Verify that the number of threads decreased
        self.assertTrue(len(worker.threads) <= worker.thread_count, "Worker did not scale down correctly")

        worker.stop_workers()

    @patch('redis.Redis.from_url')
    @patch('redis.Redis.llen')
    def test_worker_scaling_down(self, mock_redis_llen, mock_redis_from_url):
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance
        mock_redis_llen.return_value = 19  # Simulate a low queue size

        worker = RedisWorker()
        worker.start_workers()

        time.sleep(1)  # Allow time for scaling

        self.assertTrue(len(worker.threads) <= worker.thread_count, "Worker did not scale down correctly")

        worker.stop_workers()

    def tearDown(self):
        close_connections()
        if hasattr(self.worker, 'threads'):
            for t in self.worker.threads:
                t.join()
        if hasattr(self.worker, 'monitor_thread') and self.worker.monitor_thread:
            self.worker.monitor_thread.join()

if __name__ == '__main__':
    import unittest
    unittest.main()
