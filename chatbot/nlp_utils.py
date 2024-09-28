# nlp_utils.py
import re

# Common Spanish stopwords that don't provide useful information
SPANISH_STOPWORDS = {"de", "la", "el", "que", "y", "en", "a", "los", "por", "con", "para", "del"}

def clean_text(text):
    """Remove punctuation and convert text to lowercase."""
    text = text.lower()  # Convert to lowercase for uniformity
    text = re.sub(r'[^\w\s]', '', text)  # Remove any punctuation
    return text.strip()  # Remove leading/trailing spaces

def tokenize(text):
    """Split the cleaned text into individual words (tokens)."""
    return text.split()  # Split the string into words

def preprocess(text):
    """
    Clean the input text, tokenize it, and remove stopwords.
    Returns the processed tokens.
    """
    text = clean_text(text)  # First clean the text
    tokens = tokenize(text)  # Tokenize the cleaned text
    # Remove tokens that are in the list of stopwords
    return [token for token in tokens if token not in SPANISH_STOPWORDS]
