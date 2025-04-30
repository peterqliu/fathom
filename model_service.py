from sentence_transformers import SentenceTransformer
import logging
import os
import numpy as np
from threading import Thread, Event
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json
from dotenv import load_dotenv
from constants import CONFIG_FILE, MODELS_DIR
from watch import remove_file_embeddings
from watch import FileHandler

logger = logging.getLogger(__name__)

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, logger):
        self.logger = logger

    def on_created(self, event):
        if not event.is_directory:
            self.logger.info(f"File created: {event.src_path}")
            self.logger.info('--------------------------------')

    def on_deleted(self, event):
        if not event.is_directory:
            self.logger.info(f"File deleted: {event.src_path}")
            self.logger.info('--------------------------------')
            
    def on_moved(self, event):
        if not event.is_directory:
            self.logger.info(f"File renamed/moved:")
            self.logger.info(f"  from: {event.src_path}")
            self.logger.info(f"  to: {event.dest_path}")
            self.logger.info('--------------------------------')

class ModelService:
    def __init__(self, models_dir: str = MODELS_DIR):
        self.models_dir = models_dir
        self.model = None
        self.ready = Event()
        
        # Define model cache directory
        self.model_name = 'BAAI/bge-small-en'
        
        # Initialize model in background
        self.init_thread = Thread(target=self.initialize_model)
        self.init_thread.start()

        # Set up file system observer
        self.setup_file_watcher()
    
    def setup_file_watcher(self):
        """Set up the file system observer to watch for changes"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                file_directory = config.get('targetDirectory')
                if not file_directory:
                    raise ValueError("targetDirectory not found in config file")
                file_directory = os.path.expanduser(file_directory)  # Expand ~ to home directory
        except FileNotFoundError:
            raise ValueError(f"Config file not found at {CONFIG_FILE}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in config file at {CONFIG_FILE}")

        self.event_handler = FileHandler()
        self.observer = Observer()
        self.observer.schedule(self.event_handler, file_directory, recursive=False)
        self.observer.start()
        logger.info(f"Started watching directory: {file_directory}")
    
    def initialize_model(self):
        try:
            # Check if model is cached
            model_path = os.path.join(self.models_dir, self.model_name.split('/')[-1])
            if not os.path.exists(model_path):
                logger.info(f"Downloading and caching model {self.model_name}...")
                os.makedirs(model_path, exist_ok=True)
                temp_model = SentenceTransformer(self.model_name)
                temp_model.save(model_path)
                logger.info(f"Model cached successfully at {model_path}")
            else:
                logger.info(f"Model already cached at {model_path}")

            # Initialize model from cache
            self.model = SentenceTransformer(model_path)
            # Warmup with a larger batch to ensure model is fully loaded
            self.model.encode(["warmup"] * 32, convert_to_numpy=True)
            self.ready.set()  # Signal that the model is ready
            logger.info("Model loaded and ready!")
            
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

    def cleanup(self):
        """Clean up resources when shutting down"""
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
            logger.info("File watcher stopped") 