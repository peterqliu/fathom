import os
import threading
import numpy as np
from constants import MODELS_DIR
import multiprocessing as mp
from sentence_transformers import SentenceTransformer
os.environ["TOKENIZERS_PARALLELISM"] = "false"

mp.set_start_method("spawn", force=True)

class EmbeddingModel:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EmbeddingModel, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, model_name='BAAI/bge-small-en'):
        if self._initialized:
            return
        self.model_name = model_name
        self.cache_dir = MODELS_DIR
        self.model = None
        # We'll load the model in a separate thread to keep the UI responsive
        self.loading_thread = threading.Thread(target=self.load_model)
        self.loading_thread.daemon = True
        self.loading_thread.start()
        self._initialized = True
        
    def load_model(self):
        # Check for cached model
        local_model_path = os.path.join(self.cache_dir, self.model_name.split('/')[-1])
        if not os.path.exists(local_model_path):
            print(f"Downloading and caching model {self.model_name}...")
            os.makedirs(local_model_path, exist_ok=True)
            temp_model = SentenceTransformer(self.model_name)
            temp_model.save(local_model_path)
            print(f"Model cached successfully at {local_model_path}")
        else:
            print(f"Using cached model from {local_model_path}")
            
        # Load model from cache
        self.model = SentenceTransformer(local_model_path)
        # Warmup
        self.model.encode(["warmup"] * 8, convert_to_numpy=True)
        print("Model loaded and ready!")
    
    def is_ready(self):
        return self.model is not None
    
    def encode(self, text):
        """Encode a single text string and return its embedding"""
        if not self.is_ready():
            return None  # Or raise an exception
        
        if isinstance(text, str):
            embedding = self.model.encode([text], convert_to_numpy=True)[0]
            return embedding
        else:
            raise ValueError("Input must be a string for encode method")
    
    def encode_batch(self, texts, batch_size=32):
        """Encode a list of texts and return their embeddings
        
        Args:
            texts (list): List of text strings to encode
            batch_size (int, optional): Batch size for encoding. Defaults to 32.
            
        Returns:
            numpy.ndarray: 2D array of embeddings with shape (len(texts), embedding_dim)
        """
        if not self.is_ready():
            return None  # Or raise an exception
        
        if not isinstance(texts, list):
            raise ValueError("Input must be a list of strings for encode_batch method")
        
        # Check if list is empty
        if len(texts) == 0:
            return np.array([])
            
        # Process in batches to avoid memory issues with very large inputs
        if len(texts) <= batch_size:
            # Process all at once if smaller than batch_size
            return self.model.encode(texts, convert_to_numpy=True)
        else:
            # Process in batches for larger inputs
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                batch_embeddings = self.model.encode(batch, convert_to_numpy=True)
                all_embeddings.append(batch_embeddings)
            
            # Combine all batch results
            return np.vstack(all_embeddings)