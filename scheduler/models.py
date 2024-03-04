from django.db import models


class Event(models.Model):
    title = models.CharField(max_length=200)
    day = models.CharField(max_length=20)
    startTime = models.TimeField()
    endTime = models.TimeField()
    description = models.TextField()

    def __str__(self):
        return self.title
