# consumers.py
import base64
import cv2
import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from asgiref.sync import async_to_sync
from celery.result import AsyncResult
from .tasks import process_pose

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
        task = process_pose.delay(image)

        # Send an initial response indicating that processing is in progress
        await self.send(text_data=json.dumps({
            'pose_result': 'Pose detection and correctness in progress'
        }))

        # Wait for the Celery task to complete and send back the result
        while not task.ready():
            await asyncio.sleep(1)  # Check every second

        if task.successful():
            response = task.result
            await self.send(text_data=json.dumps(response))
        else:
            await self.send(text_data=json.dumps({'pose_result': 'Error processing the pose'}))
