from sentence_transformers import SentenceTransformer
import logging
import os
import numpy as np
from threading import Thread, Event
import sys

logger = logging.getLogger(__name__)

class ModelService:
    def __init__(self, models_dir: str, store_file: str):
        self.store_file = store_file
        self.models_dir = models_dir
        
        self.model = None
        self.ready = Event()
        
        # Define model cache directory
        self.model_name = 'BAAI/bge-large-en'
        
        # Initialize model in background
        self.init_thread = Thread(target=self.initialize_model)
        self.init_thread.start()
    
    def initialize_model(self):
        try:
            # Check if model is cached
            model_path = os.path.join(self.models_dir, self.model_name.split('/')[-1])
            if not os.path.exists(model_path):
                os.makedirs(model_path, exist_ok=True)
                temp_model = SentenceTransformer(self.model_name)
                temp_model.save(model_path)

            # Initialize model from cache
            self.model = SentenceTransformer(model_path)
            self.model.encode(["warmup"])  # Warmup encoding
            self.ready.set()  # Signal that the model is ready
            
        except Exception as e:
            logger.error("Failed to initialize model: %s", str(e))
            raise
    
    def encode(self, query) -> np.ndarray:
        """
        Encode a query string or list of strings to embedding vector(s)
        
        Args:
            query: A string or list of strings to encode
            
        Returns:
            np.ndarray: The embedding vector(s)
        """
        if not self.ready.is_set():
            raise RuntimeError("Model not yet initialized")
        
        try:
            # Convert single string to list
            if isinstance(query, str):
                query = [query]
            
            # Ensure query is a list
            if not isinstance(query, list):
                raise ValueError(f"Query must be a string or list of strings, got {type(query)}")
            
            # Encode all strings
            embeddings = self.model.encode(query, convert_to_numpy=True)
            
            # If single string was provided, return single embedding
            if len(query) == 1:
                return embeddings[0]
            
            return embeddings
            
        except Exception as e:
            logger.error("Encoding error: %s", str(e))
            raise
    
    def is_ready(self) -> bool:
        """Check if the model is ready"""
        return self.ready.is_set()
    
    def wait_until_ready(self, timeout=None) -> bool:
        """Wait until the model is ready"""
        return self.ready.wait(timeout=timeout) 