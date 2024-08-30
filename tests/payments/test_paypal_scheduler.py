from datetime import datetime, timedelta
from payments.paypal_scheduler import SchedulerSingleton
from django_apscheduler.models import DjangoJob, DjangoJobExecution
from django.test import TestCase
import logging
import time

logger = logging.getLogger("payments")


class TestSchedulerJob(TestCase):
    def test_simple_job_creation_and_execution(self):
        scheduler = SchedulerSingleton.get_instance()
        run_time = datetime.utcnow() + timedelta(
            seconds=10
        )  # Schedule to run in 10 seconds

        # Schedule the job
        job = scheduler.add_job(
            func=print,
            trigger="date",
            run_date=run_time,
            args=["This is a test job."],
            id="test_simple_job",
            replace_existing=True,
        )
        logger.info(f"Test job scheduled for {run_time.isoformat()}")

        time.sleep(5)
        # Verify the job was created
        job_exists = DjangoJob.objects.filter(id="test_simple_job").exists()
        self.assertTrue(job_exists, "The job was not created in the DjangoJob table.")

        # Wait for the job to be executed
        time.sleep(15)  # Wait 15 seconds to ensure the job has time to execute

        # Verify the job was executed
        job_execution_exists = DjangoJobExecution.objects.filter(
            job_id="test_simple_job"
        ).exists()
        self.assertTrue(
            job_execution_exists,
            "The job was not executed and recorded in the DjangoJobExecution table.",
        )

        # Check the status of the job execution
        job_execution = DjangoJobExecution.objects.get(job_id="test_simple_job")
        self.assertEqual(job_execution.status, "S", "The job did not succeed.")

        logger.info("The test job was successfully created, executed, and verified.")
