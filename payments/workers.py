import threading
import redis
import json
import uuid
import time
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from django.conf import settings
from payments.processing import process_event
import stripe
import logging
import os
from dotenv import load_dotenv

load_dotenv(".env.dev")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

logger = logging.getLogger("django")

class RedisWorker:

    def __init__(self):
        self.redis_conn = redis.ConnectionPool.from_url(settings.REDIS_URL)
        self.redis_client = redis.Redis(connection_pool=self.redis_conn)
        self.thread_count = 2
        self.max_threads = 10
        self.min_threads = 2
        self.shutdown_event = threading.Event()
        self.threads = []
        self.thread_connections = {}
        self.lock = threading.Lock()
        self.event_lock = threading.Lock()
        self.processing_events = set()
        self.monitor_thread = None
        self.MAX_RETRIES = 3
        logger.info("RedisWorker initialized with settings: "
                    f"thread_count={self.thread_count}, max_threads={self.max_threads}, min_threads={self.min_threads}")

    def start_workers(self):
        for _ in range(self.thread_count):
            self.add_thread()
        self.start_monitoring()

    def worker(self):
        thread_name = threading.current_thread().name
        logger.info(f"{thread_name} started processing")
        conn = None
        cur = None
        try:
            if settings.DEBUG:
                conn = psycopg2.connect(
                    dbname=settings.DATABASES['default']['NAME'],
                    user=settings.DATABASES['default']['USER'],
                    password=settings.DATABASES['default']['PASSWORD'],
                    host=settings.DATABASES['default']['HOST'],
                    port=settings.DATABASES['default']['PORT']
                )
            else:
                database_url = os.environ.get('DATABASE_URL')
                conn = psycopg2.connect(database_url)
            conn.autocommit = True
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            self.thread_connections[thread_name] = conn

            while not self.shutdown_event.is_set():
                event = None
                try:
                    message = self.redis_client.blpop('task_queue', timeout=1)
                    if message:
                        _, data = message
                        task_data = json.loads(data)
                        event = stripe.Event.construct_from(task_data, stripe.api_key)
                        logger.info(f"Stripe event {event.type} received with ID {event.id}")

                        process_it = False

                        with self.event_lock:
                            cur.execute("SELECT EXISTS (SELECT 1 FROM payments_stripeevent WHERE stripe_event_id = %s AND status = 'processed')", (event.id,))
                            existing_event = cur.fetchone()[0]
                            if not existing_event and event.id not in self.processing_events:
                                self.processing_events.add(event.id)
                                process_it = True

                        if process_it:
                            retries = 0
                            while retries < self.MAX_RETRIES:
                                try:
                                    cur.execute("BEGIN;")
                                    if process_event(event, cur):
                                        cur.execute(
                                            """
                                            INSERT INTO payments_stripeevent (stripe_event_id, created_at, status)
                                            VALUES (%s, %s, %s)
                                            ON CONFLICT (stripe_event_id) DO UPDATE SET status = EXCLUDED.status
                                            """,
                                            (event.id, datetime.now(timezone.utc), 'processed')
                                        )
                                        cur.execute("COMMIT;")
                                        logger.info(f"Event {event.id} processed successfully")
                                    break
                                except Exception as e:
                                    retries += 1
                                    cur.execute("ROLLBACK;")
                                    logger.error(f"Error processing Stripe webhook for event {event.id}: {e}. Retry {retries}/{self.MAX_RETRIES}", exc_info=True)
                                    if retries == self.MAX_RETRIES:
                                        cur.execute(
                                            """
                                            INSERT INTO payments_stripeevent (stripe_event_id, created_at, status)
                                            VALUES (%s, %s, %s)
                                            ON CONFLICT (stripe_event_id) DO UPDATE SET status = EXCLUDED.status
                                            """,
                                            (event.id, datetime.now(timezone.utc), 'failed')
                                        )
                            with self.event_lock:
                                self.processing_events.remove(event.id)
                        else:
                            logger.info(f"{thread_name} skipped event {event.id} (already being processed or already processed)")
                    else:
                        time.sleep(1)
                except redis.exceptions.TimeoutError:
                    logger.warning(f"{thread_name} timed out waiting for message")
                    continue
                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)
                    if event is not None:
                        with self.event_lock:
                            if event.id in self.processing_events:
                                self.processing_events.remove(event.id)
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
            if thread_name in self.thread_connections:
                del self.thread_connections[thread_name]

    def add_thread(self):
        unique_id = str(uuid.uuid4())
        t = threading.Thread(target=self.worker, name=f"WorkerThread-{unique_id}")
        t.daemon = True
        with self.lock:
            self.threads.append(t)
        t.start()
        logger.info(f"Added new worker thread {t.name}")

    def remove_thread(self):
        if len(self.threads) > self.min_threads:
            with self.lock:
                thread_to_remove = self.threads.pop()
            logger.info(f"Removing worker thread {thread_to_remove.name}")
            self.shutdown_event.set()  # Signal the thread to stop
            thread_to_remove.join()
            logger.info(f"Removed worker thread {thread_to_remove.name}")
            self.shutdown_event.clear()  # Clear the shutdown event for other threads

    def scale_threads(self):
        queue_size = self.redis_client.llen('task_queue')
        with self.lock:
            current_threads = len(self.threads)
        if queue_size > 50 and current_threads < self.max_threads:
            logger.info("Scaling up: adding a thread due to high queue size")
            self.add_thread()
        elif queue_size < 20 and current_threads > self.min_threads:
            logger.info("Scaling down: removing a thread due to low queue size")
            self.remove_thread()

    def monitor_and_scale(self):
        while not self.shutdown_event.is_set():
            self.scale_threads()
            threading.Event().wait(30)  # Check every 30 seconds

    def start_monitoring(self):
        self.monitor_thread = threading.Thread(target=self.monitor_and_scale, name="MonitorThread")
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("Started monitoring thread for scaling workers")

    def stop_workers(self):
        logger.info("Stopping all worker threads")
        self.shutdown_event.set()  # Signal all threads to stop
        for t in self.threads:
            t.join()  # Wait for all threads to finish
            logger.info(f"Stopped worker thread {t.name}")

        if self.monitor_thread:
            self.monitor_thread.join()
            logger.info("Stopped monitoring thread")

def on_django_shutdown(worker):
    worker.stop_workers()
