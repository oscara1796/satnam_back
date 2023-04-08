from rest_framework import serializers
from .models import Video

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['id', 'title', 'image', 'description', 'url', 'free','date_of_creation', 'date_of_modification']
