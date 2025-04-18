import os
import sys

# Base application paths
APP_NAME = "Fathom"
APP_SUPPORT_PATH = os.path.expanduser('~/Library/Application Support/Fathom')

# Directory paths
INDEX_DIR = os.path.join(APP_SUPPORT_PATH, 'index')
MODELS_DIR = os.path.join(APP_SUPPORT_PATH, 'models')
CONSTANTS_DIR = os.path.join(APP_SUPPORT_PATH, 'constants')

# File paths
CONFIG_FILE = os.path.join(CONSTANTS_DIR, 'config.json')
STORE_FILE = os.path.join(APP_SUPPORT_PATH, 'content_store.json')

# Index file paths
os.makedirs(INDEX_DIR, exist_ok=True)  # Create index directory before defining files in it
VECTOR_INDEX_FILE = os.path.join(INDEX_DIR, 'vectorIndex')
CLUSTERS_FILE = os.path.join(INDEX_DIR, 'clusters.json')
SQLITE_DB_FILE = os.path.join(INDEX_DIR, 'sentences.db')

# NLTK data initialization
def ensure_nltk_data():
    """Ensure NLTK data is downloaded only if not already present"""
    try:
        import nltk
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

# Creates all required application directories
def ensure_directories():
    """Create all required application directories"""
    for directory in [APP_SUPPORT_PATH, INDEX_DIR, MODELS_DIR, CONSTANTS_DIR]:
        os.makedirs(directory, exist_ok=True) 