from django.db import models

class Video(models.Model):
    # id = models.AutoField(primary_key=True, default=1)
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='videos')
    description = models.TextField()
    url = models.TextField() 
    free = models.BooleanField(default=False)
    date_of_creation = models.DateTimeField(auto_now_add=True)
    date_of_modification = models.DateTimeField(auto_now=True)
    categories = models.ManyToManyField('Category', related_name='category_videos')

    
    def __str__(self):
        return self.title


class Category(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    videos = models.ManyToManyField('Video', related_name='video_categories')

    def __str__(self):
        return self.title