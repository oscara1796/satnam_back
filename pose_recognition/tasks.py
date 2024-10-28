# tasks.py
from celery import shared_task, Task
import tensorflow as tf
import numpy as np
import mediapipe as mp
import cv2
import pickle
import logging
import time
import os

# Configure logging
logger = logging.getLogger("videos")

# Load the saved model and label encoder
logger.info("Loading model and label encoder...")
model = tf.keras.models.load_model('yoga_pose_model.h5')
logger.info("Model loaded successfully.")
with open('label_encoder.pkl', 'rb') as f:
    label_encoder = pickle.load(f)
logger.info("Label encoder loaded successfully.")

# Mediapipe setup for pose extraction
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.3, model_complexity=0)

# Custom task class to allow for timeouts
class BaseTaskWithTimeout(Task):
    time_limit = 120  # 30 seconds maximum runtime for the task

@shared_task(bind=True, base=BaseTaskWithTimeout)
def process_pose(self, image_bytes):
    try:
        logger.info("Starting pose processing task")
        
        start_time = time.time()

        # Create a directory to store debug images if it doesn't exist
        # debug_dir = 'debug_images'
        # if not os.path.exists(debug_dir):
        #     os.makedirs(debug_dir)
        
        # Convert byte array back to an image
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        logger.info(f"Image decoded successfully, shape: {image.shape}")

        # # Save the original image for debugging
        # original_image_path = os.path.join(debug_dir, 'original_image.jpg')
        # cv2.imwrite(original_image_path, image)
        # logger.info(f"Original image saved at {original_image_path}")

        # Convert image to RGB for Mediapipe
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        logger.info(f"Image converted to RGB, shape: {rgb_image.shape}")

        # # Save the RGB image for debugging
        # rgb_image_path = os.path.join(debug_dir, 'rgb_image.jpg')
        # cv2.imwrite(rgb_image_path, cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR))  # Convert back to BGR for saving
        # logger.info(f"RGB image saved at {rgb_image_path}")

        # Resize the image to reduce processing time
        resized_rgb_image = cv2.resize(rgb_image, (160, 120))
        logger.info(f"Image resized to: {resized_rgb_image.shape}")

        # # Save the resized image for debugging
        # resized_image_path = os.path.join(debug_dir, 'resized_image.jpg')
        # cv2.imwrite(resized_image_path, cv2.cvtColor(resized_rgb_image, cv2.COLOR_RGB2BGR))  # Convert back to BGR for saving
        # logger.info(f"Resized image saved at {resized_image_path}")

        # Process with Mediapipe to extract landmarks
        logger.info("Extracting pose landmarks...")
        results = pose.process(resized_rgb_image)

        if not results.pose_landmarks:
            logger.warning("No keypoints detected")
            return {'error': 'No keypoints detected'}

        # Draw landmarks on the resized image for debugging
        # landmark_image = resized_rgb_image.copy()
        # mp_drawing = mp.solutions.drawing_utils
        # mp_drawing.draw_landmarks(
        #     landmark_image,
        #     results.pose_landmarks,
        #     mp_pose.POSE_CONNECTIONS
        # )

        # # Save the image with landmarks for debugging
        # landmarks_image_path = os.path.join(debug_dir, 'landmarks_image.jpg')
        # cv2.imwrite(landmarks_image_path, cv2.cvtColor(landmark_image, cv2.COLOR_RGB2BGR))  # Convert back to BGR for saving
        # logger.info(f"Landmarks image saved at {landmarks_image_path}")

        # Extract and flatten keypoints for prediction
        keypoints = [[landmark.x, landmark.y, landmark.z] for landmark in results.pose_landmarks.landmark]
        keypoints_flattened = np.array(keypoints).flatten().reshape(1, -1)
        logger.info(f"Keypoints extracted and flattened, shape: {keypoints_flattened.shape}")

        # Predict the pose and correctness
        logger.info("Starting model prediction")
        with tf.device('/CPU:0'):  # Use CPU for prediction to avoid GPU issues
            predictions = model.predict(keypoints_flattened)
        logger.info("Model prediction completed")

        # Decode pose label and correctness
        pose_prediction = predictions[0]
        correctness_prediction = predictions[1]

        pose_label_index = np.argmax(pose_prediction)
        pose_label = label_encoder.inverse_transform([pose_label_index])[0]
        correctness = 'Yes' if correctness_prediction > 0.5 else 'No'

        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        logger.info(f"Task completed in {elapsed_time:.2f} seconds")

        # Return a single response
        response = {
            'pose_label': pose_label,
            'is_correct': correctness
        }
        logger.info(f"Task completed successfully with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error processing the pose: {str(e)}")
        return {'error': f'Error processing the pose: {str(e)}'}
