# tasks.py
from celery import shared_task
import tensorflow as tf
import numpy as np
import mediapipe as mp
import cv2
import json
import pickle
from django.core.cache import cache

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
def process_pose(self, images):
    batch_keypoints = []
    for image in images:
        # Convert image to RGB for Mediapipe
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_image)

        if results.pose_landmarks:
            keypoints = [[landmark.x, landmark.y, landmark.z] for landmark in results.pose_landmarks.landmark]
            batch_keypoints.append(np.array(keypoints).flatten())

    if not batch_keypoints:
        return {'error': 'No keypoints detected'}

    # Convert batch_keypoints to numpy array for prediction
    keypoints_batch = np.array(batch_keypoints)

    # Predict the pose and correctness
    with tf.device('/GPU:0'):  # Specify that this task should use GPU 0
        predictions = model.predict(keypoints_batch)

    responses = []
    for i in range(len(predictions[0])):
        pose_prediction = predictions[0][i]
        correctness_prediction = predictions[1][i]

        # Decode pose label and correctness
        pose_label_index = np.argmax(pose_prediction)
        pose_label = label_encoder.inverse_transform([pose_label_index])[0]
        correctness = 'Yes' if correctness_prediction > 0.5 else 'No'

        responses.append({
            'pose_label': pose_label,
            'is_correct': correctness
        })

    # Store result in cache
    cache_key = f'pose_task_{self.request.id}'
    cache.set(cache_key, responses, timeout=60*5)  # Cache result for 5 minutes
    return responses
