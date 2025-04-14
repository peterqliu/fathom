import requests
import numpy as np
import os
import sys
import json
from constants import CONFIG_FILE, INDEX_DIR

def get_index_dir():
    """Get the appropriate index directory path"""
    # Create directory if it doesn't exist
    os.makedirs(INDEX_DIR, exist_ok=True)
    return INDEX_DIR

def get_embedding(sentence: str, model_url: str = 'http://localhost:5000/encode') -> np.ndarray:
    """
    Get embedding for a single sentence from the model service.
    
    Args:
        sentence (str): The sentence to get embedding for
        model_url (str): URL of the model service endpoint
        
    Returns:
        np.ndarray: The embedding vector
        
    Raises:
        ValueError: If the request fails or returns invalid response
    """
    response = requests.post(model_url, json={'query': sentence})
    if response.status_code != 200:
        raise ValueError(f"Failed to get embedding: {response.text}")
    
    embedding = np.array(response.json()['embedding'])
    return embedding

def get_embeddings_batch(sentences: list[str], model_url: str = 'http://localhost:5000/encode_batch') -> np.ndarray:
    """
    Get embeddings for a batch of sentences from the model service.
    
    Args:
        sentences (list[str]): List of sentences to get embeddings for
        model_url (str): URL of the model service batch endpoint
        
    Returns:
        np.ndarray: Array of embedding vectors
        
    Raises:
        ValueError: If the request fails or returns invalid response
    """
    response = requests.post(model_url, json={'queries': sentences})
    if response.status_code != 200:
        raise ValueError(f"Failed to get embeddings: {response.text}")
    
    embeddings = np.array(response.json()['embeddings'])
    return embeddings

def get_target_directory():
    """
    Read and return the target directory from the config file.
    
    Returns:
        str: The target directory path
        
    Raises:
        ValueError: If config file is missing, invalid, or missing targetDirectory
    """
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            directory = config.get('targetDirectory')
            if not directory:
                raise ValueError("targetDirectory not found in config file")
            return os.path.expanduser(directory)  # Expand ~ to home directory
    except FileNotFoundError:
        raise ValueError(f"Config file not found at {CONFIG_FILE}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in config file at {CONFIG_FILE}") 