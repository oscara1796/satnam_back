from rest_framework import serializers
from .models import Video

class VideoSerializer(serializers.ModelSerializer):

    def validate(self, data):
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
        fields = ('id', 'title', 'image', 'description', 'url', 'free','date_of_creation', 'date_of_modification')
