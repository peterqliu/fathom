import os
import sys
import json

# Base application paths
APP_NAME = "Fathom"
APP_SUPPORT_PATH = os.path.expanduser('~/Library/Application Support/Fathom')

# Directory paths
INDEX_DIR = os.path.join(APP_SUPPORT_PATH, 'index')
MODELS_DIR = os.path.join(APP_SUPPORT_PATH, 'models')

# File paths
CONFIG_FILE = os.path.join(APP_SUPPORT_PATH, 'config.json')
# STORE_FILE = os.path.join(APP_SUPPORT_PATH, 'content_store.json')

# Index file paths
os.makedirs(INDEX_DIR, exist_ok=True)  # Create index directory before defining files in it
VECTOR_INDEX_FILE = os.path.join(INDEX_DIR, "vectorIndex")
SQLITE_DB_FILE = os.path.join(INDEX_DIR, "sentences.db")

# Debug states
DEBUG_SKIP_INDEXING = False
DEBUG_SKIP_DELETING = False

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
    for directory in [APP_SUPPORT_PATH, INDEX_DIR, MODELS_DIR]:
        os.makedirs(directory, exist_ok=True) 
    
    # Create config.json if it doesn't exist
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"target": None}, f) 

class Config:
    @staticmethod
    def getTargetDirectory():
        """Read the config file and return the target directory value"""
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config["target"] if config["target"] is not None else '.'
    
    @staticmethod
    def setTargetDirectory(directory):
        """Set the target directory in the config file"""
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        config["target"] = directory
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

# # Legacy function for backwards compatibility
# def get_target():
#     """Read the config file and return the target value (legacy function)"""
#     return Config.getTargetDirectory() 