import threading
import redis
import json
import uuid 
from django.conf import settings
from payments.processing import process_event

class RedisWorker:
    def __init__(self):
        self.redis_conn = redis.Redis.from_url(settings.REDIS_URL)
        self.thread_count = 2
        self.max_threads = 10
        self.min_threads = 2
        self.shutdown_event = threading.Event()
        self.threads = []
        self.lock = threading.Lock()
        self.monitor_thread = None 

    def start_workers(self):
        for _ in range(self.thread_count):
            self.add_thread()
        self.start_monitoring() 

    def worker(self):
        import time
        count = 0
        thread_name = threading.current_thread().name
        print(f"{thread_name} started processing")
        while not self.shutdown_event.is_set():
            time.sleep(2)
            print(f"{thread_name} processing data: {count}")
            count+=1

            # try:
            #     message = self.redis_conn.blpop('task_queue', timeout=1)
            #     if message:
            #         _, data = message
            #         task_data = json.loads(data)
            #         process_event(task_data)
            # except redis.exceptions.TimeoutError:
            #     continue
            # except Exception as e:
            #     print(f"Error processing message: {e}")
    
    def add_thread(self):
        unique_id = str(uuid.uuid4())
        t = threading.Thread(target=self.worker, name=f"WorkerThread-{unique_id}")
        t.daemon = True
        with self.lock:
            self.threads.append(t)
        t.start()
    
    def remove_thread(self):
        if len(self.threads) > self.min_threads:
            with self.lock:
                thread_to_remove = self.threads.pop()
            thread_to_remove.join()
    
    def scale_threads(self):
        queue_size = self.redis_conn.llen('task_queue')
        with self.lock:
            current_threads = len(self.threads)
        if queue_size > 50 and current_threads < self.max_threads:
            self.add_thread()
        elif queue_size < 20 and current_threads > self.min_threads:
            self.remove_thread()
    
    def monitor_and_scale(self):
        while not self.shutdown_event.is_set():
            self.scale_threads()
            threading.Event().wait(30)  # Check every 30 seconds

    def start_monitoring(self):  # Add this method
        self.monitor_thread = threading.Thread(target=self.monitor_and_scale, name="MonitorThread")
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_workers(self):
        self.shutdown_event.set()  # Signal all threads to stop
        for t in self.threads:
            t.join()  # Wait for all threads to finish
        
         if self.monitor_thread:
            self.monitor_thread.join()

def on_django_shutdown(worker):
    worker.stop_workers()
