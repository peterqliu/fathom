import requests
import numpy as np
import os
import sys

def get_index_dir():
    """Get the appropriate index directory path"""
    if getattr(sys, 'frozen', False):
        # We are running in a bundle
        app_support = os.path.expanduser('~/Library/Application Support/Fathom')
        index_dir = os.path.join(app_support, 'index')
    else:
        # We are running in development
        index_dir = os.path.abspath('index')
    
    # Create directory if it doesn't exist
    os.makedirs(index_dir, exist_ok=True)
    return index_dir

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