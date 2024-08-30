from django.apps import AppConfig
import logging
from django.db.models.signals import post_migrate


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"

    def ready(self):
        pass
        # from payments.workers import RedisWorker, on_django_shutdown
        # import atexit

        # # Configure the logger for this module
        # logger = logging.getLogger("payments")

        # # Log the startup message
        # logger.info("Payments application has started. Setting up RedisWorker to process payments.")

        # # Create and start the RedisWorker
        # self.redis_worker = RedisWorker()
        # self.redis_worker.start_workers()

        # # Register the shutdown function
        # atexit.register(on_django_shutdown, self.redis_worker)

        # # Log the message indicating that workers are ready
        # logger.info("RedisWorker has been started and is now processing payments.")
