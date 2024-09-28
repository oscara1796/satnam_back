# tasks.py
from celery import shared_task
from .models import YogaVideo
from .naive_bayes_classifier import NaiveBayesClassifier
from .ner import named_entity_recognition
from .tfidf import compute_tfidf
from .cosine_similarity import cosine_similarity
from .levenshtein_distance import fuzzy_match
from .nlp_utils import preprocess

# Initialize the Naive Bayes Classifier
classifier = NaiveBayesClassifier()
training_data = [
    ("¿Cuáles son los beneficios del yoga?", "beneficios"),
    ("¿El yoga ayuda con el dolor de espalda?", "beneficios"),
    ("Muéstrame yoga para principiantes", "recomendacion"),
]
classifier.train(training_data)





@shared_task
def chatbot_task(user_message):
    """
    Celery task to process user input and return a chatbot response.
    """
    if user_message:
        tokens = preprocess(user_message)  # Preprocess the input text

        # Predict intent using Naive Bayes
        intent = classifier.predict(user_message)

        # Identify named entities in the input
        entities = named_entity_recognition(user_message)

        # Handle fuzzy matching for misspelled words
        known_tokens = ["beneficios", "recomendacion", "dolor", "espalda", "flexibilidad"]
        for token in tokens:
            match = fuzzy_match(token, known_tokens)
            if match:
                tokens.append(match)  # Add the corrected word to the token list

        # Compute TF-IDF vector for user input
        user_tfidf = compute_tfidf([(user_message, 'unknown')])

        # Compare input with training data using cosine similarity
        similarities = []
        for intent, vector in tfidf_scores.items():
            similarity = cosine_similarity(user_tfidf, vector)
            similarities.append((intent, similarity))

        predicted_intent = max(similarities, key=lambda x: x[1])[0]  # Get the most similar intent

        # Handle recommendations
        if predicted_intent == 'recomendacion':
            response = recommend_video(entities)
        elif predicted_intent == 'beneficios':
            response = "El yoga te ayuda a mejorar la flexibilidad, reducir el estrés y fortalecer los músculos."
        else:
            response = "No estoy seguro de esa respuesta, pero puedo buscar más información."
    else:
        response = "¡Por favor, hazme una pregunta sobre yoga!"

    return response