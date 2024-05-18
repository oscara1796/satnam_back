import threading
import redis
import json
import uuid
from dotenv import dotenv_values
from django.conf import settings
from payments.processing import process_event
import stripe
import logging
from .models import StripeEvent

env_vars = dotenv_values(".env.dev")
stripe.api_key = env_vars["STRIPE_SECRET_KEY"]

logger = logging.getLogger("django")

class RedisWorker:
    


    def __init__(self):
        self.redis_conn = redis.Redis.from_url(settings.REDIS_URL)
        self.thread_count = 2
        self.max_threads = 10
        self.min_threads = 2
        self.shutdown_event = threading.Event()
        self.threads = []
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
        import time
        count = 0
        thread_name = threading.current_thread().name
        logger.info(f"{thread_name} started processing")
        while not self.shutdown_event.is_set():
            try:
                message = self.redis_conn.blpop('task_queue', timeout=1)
                if message:
                    _, data = message
                    task_data = json.loads(data)
                    event = stripe.Event.construct_from(task_data, stripe.api_key)
                    logger.info(f"Stripe event {event.type} received with ID {event.id}")

                    process_it = False 

                    with self.event_lock:
                        if event.id not in self.processing_events:
                            self.processing_events.add(event.id)
                            process_it = True 
                    
                    if process_it:
                        retries = 0
                        while retries < self.MAX_RETRIES:
                            try:
                                process_event(event)
                                self.update_event_status(event.id, 'processed')
                                logger.info(f"Event {event.id} processed successfully")
                                break
                            except Exception as e:
                                retries += 1
                                logger.error(f"Error processing Stripe webhook for event {event.id}: {e}. Retry {retries}/{self.MAX_RETRIES}", exc_info=True)
                                if retries == self.MAX_RETRIES:
                                    self.update_event_status(event.id, 'failed')
                        with self.event_lock:
                            self.processing_events.remove(event.id)
                    else:
                        logger.info(f"{thread_name} skipped event {event_id} (already being processed)")

            except redis.exceptions.TimeoutError:
                logger.warning(f"{thread_name} timed out waiting for message")
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)
    
    def update_event_status(self, event_id, status):
        try:
            event, created = StripeEvent.objects.get_or_create(
                stripe_event_id=event.id,
                defaults={'status': 'processing'}
            )
            event.status = status
            event.save()
            self.redis_conn.hset('task_status', event_id, status)
        except StripeEvent.DoesNotExist:
            logger.error(f"Stripe event {event_id} does not exist in the database")

    
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
            thread_to_remove.join()
            logger.info(f"Removed worker thread {thread_to_remove.name}")
    
    def scale_threads(self):
        queue_size = self.redis_conn.llen('task_queue')
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
        

    def start_monitoring(self):  # Add this method
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
