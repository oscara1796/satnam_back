from django.db import models

class Video(models.Model):
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='videos')
    description = models.TextField()
    url = models.URLField()
    free = models.BooleanField(default=False)
    date_of_creation = models.DateTimeField(auto_now_add=True)
    date_of_modification = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title