# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from datetime import timedelta

class SchedulerSingleton:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance.scheduler

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_jobstore(DjangoJobStore(), "default")

        # Adding a cleanup job, assuming `max_age` should be provided
        self.scheduler.add_job(
            func=DjangoJobExecution.objects.delete_old_job_executions,
            trigger="interval",
            weeks=2,
            id="Delete old job executions",
            max_instances=1,
            replace_existing=True,
            kwargs={'max_age': timedelta(days=30)}  # max_age could be a timedelta object
        )
        self.scheduler.start()
