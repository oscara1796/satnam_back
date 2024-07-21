from django.apps import AppConfig
import logging

class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"

    def ready(self):
        from payments.workers import RedisWorker, on_django_shutdown
        import atexit
        from payments.paypal_scheduler import SchedulerSingleton

        # Configure the logger for this module
        logger = logging.getLogger("payments")

        # Log the startup message
        logger.info("Payments application has started. Setting up RedisWorker to process payments.")

        # Create and start the RedisWorker
        self.redis_worker = RedisWorker()
        self.redis_worker.start_workers()

        # Ensure the scheduler starts
        SchedulerSingleton.get_instance()
        

        # Register the shutdown function
        atexit.register(on_django_shutdown, self.redis_worker)

        # Log the message indicating that workers are ready
        logger.info("RedisWorker has been started and is now processing payments.")
        logger.info("Payments application has started. paypal scheduler is now running.")
