# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
import logging
import tensorflow as tf
import numpy as np
import pickle
import time

# Configure logging
logger = logging.getLogger("videos")
logger.setLevel(logging.DEBUG)  # Set the logging level to DEBUG to capture all logs

# Load the saved model and label encoder once at the module level
logger.info("Loading model and label encoder...")
start_time = time.time()
model = tf.keras.models.load_model('yoga_pose_model.h5')
logger.info(f"Model loaded successfully in {time.time() - start_time:.2f} seconds.")
with open('label_encoder.pkl', 'rb') as f:
    label_encoder = pickle.load(f)
logger.info("Label encoder loaded successfully.")

class YogaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        logger.info("WebSocket connection established.")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket connection closed with code: {close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            logger.debug(f"Received data: {text_data}")
            data = json.loads(text_data)
            keypoints = data.get('keypoints', None)
            if keypoints is None:
                logger.warning("No keypoints received in the data.")
                await self.send(text_data=json.dumps({'error': 'No keypoints received'}))
                return

            logger.debug("Starting to process keypoints.")
            # Process the keypoints
            response = await self.process_pose(keypoints)
            logger.debug(f"Processing complete. Sending response: {response}")
            await self.send(text_data=json.dumps(response))
        except Exception as e:
            logger.error(f"Error in receive method: {e}", exc_info=True)
            await self.send(text_data=json.dumps({'error': 'Error processing the pose'}))
            await self.close()

    async def process_pose(self, keypoints):
        try:
            logger.debug("Flattening keypoints and preparing for prediction.")
            # Flatten keypoints and prepare for prediction
            keypoints_flattened = np.array([[kp['x'], kp['y'], kp['z']] for kp in keypoints]).flatten().reshape(1, -1)
            logger.debug(f"Keypoints flattened: {keypoints_flattened.shape}")

            # Predict the pose and correctness
            logger.info("Starting model prediction.")
            prediction_start_time = time.time()
            predictions = model.predict(keypoints_flattened)
            prediction_time = time.time() - prediction_start_time
            logger.info(f"Model prediction completed in {prediction_time:.2f} seconds.")

            # Log the predictions for debugging
            logger.debug(f"Predictions: {predictions}")

            # Extract the outputs using the correct keys
            pose_prediction = predictions['pose_output']
            correctness_prediction = predictions['correctness_output']

            # Decode pose label and correctness
            logger.debug("Decoding predictions.")
            pose_label_index = np.argmax(pose_prediction, axis=1)
            pose_label = label_encoder.inverse_transform(pose_label_index)[0]

            correctness = 'Yes' if correctness_prediction[0][0] > 0.9 else 'No'

            # Return a single response
            response = {
                'pose_label': pose_label,
                'is_correct': correctness
            }
            logger.info(f"Processing completed successfully with response: {response}")
            return response

        except Exception as e:
            logger.error(f"Error processing the pose: {str(e)}", exc_info=True)
            return {'error': f'Error processing the pose: {str(e)}'}
