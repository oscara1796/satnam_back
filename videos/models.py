from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.conf import settings
import boto3
import os


class Video(models.Model):
    # id = models.AutoField(primary_key=True, default=1)
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to="videos")
    description = models.TextField()
    url = models.TextField()
    free = models.BooleanField(default=False)
    date_of_creation = models.DateTimeField(auto_now_add=True)
    date_of_modification = models.DateTimeField(auto_now=True)
    categories = models.ManyToManyField("Category", related_name="category_videos")

    def __str__(self):
        return self.title


class Category(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    videos = models.ManyToManyField("Video", related_name="video_categories")

    def __str__(self):
        return self.title


@receiver(post_delete, sender=Category)
def delete_related_videos(sender, instance, **kwargs):
    videos = instance.videos.all()
    for video in videos:
        video.delete()


@receiver(post_delete, sender=Video)
def delete_video_image(sender, instance, **kwargs):
    if instance.image:
        if settings.DEBUG:
            # Delete image locally
            if os.path.isfile(instance.image.path):
                os.remove(instance.image.path)
        else:
            # Delete image from S3
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            try:
                s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=instance.image.name)
            except Exception as e:
                print(f"Error deleting image from S3: {e}")