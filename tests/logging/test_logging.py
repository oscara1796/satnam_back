import logging
import os

from django.conf import settings
from django.test import TestCase


class LoggingTest(TestCase):
    def test_error_logging_to_file(self):
        # Ensure the logs directory exists
        logs_dir = os.path.join(settings.BASE_DIR, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # The log message to test
        test_message = "This is a test error message for logging."

        # Log an error using Django's logging system
        logger = logging.getLogger("django")
        logger.error(test_message)

        # Path to the log file
        log_file_path = os.path.join(logs_dir, "django_errors.log")

        # Check if the log file exists
        self.assertTrue(os.path.exists(log_file_path), "Log file does not exist.")

        # Read the log file and check if it contains the test message
        with open(log_file_path, "r") as log_file:
            log_contents = log_file.read()
            self.assertIn(
                test_message, log_contents, "Log message not found in log file."
            )

        # Cleanup: Remove the test log message from the log file
        # This step is optional and can be adjusted based on how you want to handle log file cleanup
        with open(log_file_path, "w") as log_file:
            log_file.write(log_contents.replace(test_message, ""))
