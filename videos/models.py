from django.db import models
from django.conf import settings
import boto3
import os
import logging

logger = logging.getLogger('django')

class Video(models.Model):
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

    def delete(self, *args, **kwargs):
        # Delete associated image file
        if self.image:
            if settings.DEBUG:
                # Delete image locally
                if os.path.isfile(self.image.path):
                    os.remove(self.image.path)
            else:
                # Delete image from S3
                s3 = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
                try:
                    s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=self.image.name)
                except Exception as e:
                    logger.error(f"Error deleting image from S3: {e}")

        super(Video, self).delete(*args, **kwargs)

class Category(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    videos = models.ManyToManyField(Video, related_name="video_categories")

    def __str__(self):
        return self.title

    def delete_with_videos(self):
        # Retrieve and delete all related videos by querying the Video model
        videos = Video.objects.filter(categories__id=self.id)
        for video in videos:
            logger.info(f"Deleting video '{video.title}' due to category deletion (ID: {self.id})")
            video.delete()

        # Delete the category
        super(Category, self).delete()
