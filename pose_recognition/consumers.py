# consumers.py
import base64
import cv2
import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from asgiref.sync import async_to_sync
from celery.result import AsyncResult
from .tasks import process_pose
from django.core.cache import cache

class YogaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        image_data = base64.b64decode(data['frame'].split(',')[1])
        np_arr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Send the image to Celery task
        task = process_pose.delay([image])  # Using batch processing, so sending a list of images

        # Store task ID in cache for tracking
        cache.set(f'pose_task_{task.id}', 'in_progress', timeout=60)

        # Send an initial response indicating that processing is in progress
        await self.send(text_data=json.dumps({
            'pose_result': 'Pose detection and correctness in progress',
            'task_id': task.id
        }))

    async def pose_result(self, task_id):
        # Retrieve the result from the cache or Celery result backend
        result = AsyncResult(task_id)
        if result.state == 'SUCCESS':
            response = result.result
            await self.send(text_data=json.dumps(response))
        elif result.state == 'FAILURE':
            await self.send(text_data=json.dumps({'pose_result': 'Error processing the pose'}))

# We will call `pose_result` once the Celery task completes using an event-driven approach.
