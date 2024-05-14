import atexit
from django.apps import AppConfig
from payments.workers import RedisWorker, on_django_shutdown

class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"

    def ready(self):
        # Assuming RedisWorker and on_django_shutdown are properly defined and imported
        self.redis_worker = RedisWorker()
        self.redis_worker.start_workers()
        atexit.register(on_django_shutdown, self.redis_worker)  # Pass the worker to the shutdown function
