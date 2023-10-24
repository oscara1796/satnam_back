from rest_framework import serializers
from .models import Video, Category
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
import base64
from PIL import Image
from io import BytesIO


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'title', 'description']




class VideoSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)

    def validate(self, data):
        # Check if 'image' field contains base64-encoded data
        

        return data

    def create(self, validated_data):
        return Video.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    class Meta:
        model = Video
        fields = ('id', 'title', 'image', 'description', 'url', 'free','date_of_creation', 'date_of_modification', 'categories')

