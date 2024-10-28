# tasks.py
from celery import shared_task
import tensorflow as tf
import numpy as np
import mediapipe as mp
import cv2
import pickle

# Load the saved model and label encoder
# Ensure TensorFlow uses the GPU if available
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    try:
        # Enable GPU memory growth
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        print("Using GPU")
    except RuntimeError as e:
        print(e)

model = tf.keras.models.load_model('yoga_pose_model.h5')
with open('label_encoder.pkl', 'rb') as f:
    label_encoder = pickle.load(f)

# Mediapipe setup for pose extraction
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)

@shared_task(bind=True)
def process_pose(self, image):
    # Convert image to RGB for Mediapipe
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb_image)

    if not results.pose_landmarks:
        return {'error': 'No keypoints detected'}

    # Extract and flatten keypoints for prediction
    keypoints = [[landmark.x, landmark.y, landmark.z] for landmark in results.pose_landmarks.landmark]
    keypoints_flattened = np.array(keypoints).flatten().reshape(1, -1)

    # Predict the pose and correctness
    device = '/GPU:0' if gpus else '/CPU:0'
    with tf.device(device):  # Use GPU if available, otherwise fall back to CPU
        predictions = model.predict(keypoints_flattened)

    # Decode pose label and correctness
    pose_prediction = predictions[0]
    correctness_prediction = predictions[1]

    pose_label_index = np.argmax(pose_prediction)
    pose_label = label_encoder.inverse_transform([pose_label_index])[0]
    correctness = 'Yes' if correctness_prediction > 0.5 else 'No'

    # Return a single response
    response = {
        'pose_label': pose_label,
        'is_correct': correctness
    }

    return response
