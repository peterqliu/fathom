from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
from waitress import serve
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from dotenv import load_dotenv
import json
from constants import MODELS_DIR, CONFIG_FILE
import numpy as np

# Initialize Flask app
app = Flask(__name__)

# Define model cache directory
model_name = 'BAAI/bge-small-en'
cache_dir = MODELS_DIR

# Download and cache model if not already cached
print(f"Checking for model in cache directory: {cache_dir}")
if not os.path.exists(os.path.join(cache_dir, model_name.split('/')[-1])):
    print(f"Downloading and caching model {model_name}...")
    os.makedirs(os.path.join(cache_dir, model_name.split('/')[-1]), exist_ok=True)
    temp_model = SentenceTransformer(model_name)
    temp_model.save(os.path.join(cache_dir, model_name.split('/')[-1]))
    print(f"Model cached successfully at {os.path.join(cache_dir, model_name.split('/')[-1])}")
else:
    print(f"Model already cached at {os.path.join(cache_dir, model_name.split('/')[-1])}")

# Initialize model from cache
# print("Loading model from cache...")
model = SentenceTransformer(os.path.join(cache_dir, model_name.split('/')[-1]))
# Warmup with a larger batch to ensure model is fully loaded
model.encode(["warmup"] * 32, convert_to_numpy=True)
print("Model loaded and ready!")

@app.route('/encode', methods=['POST'])
def encode():
    data = request.json
    query = data['query']
    embedding = model.encode([query], convert_to_numpy=True)
    # Ensure embedding is 1D before converting to list
    # embedding = np.squeeze(embedding)
    return jsonify({'embedding': embedding.tolist()})

@app.route('/encode_batch', methods=['POST'])
def encode_batch():
    data = request.json
    queries = data['queries']
    if not isinstance(queries, list):
        return jsonify({'error': 'queries must be a list'}), 400
    
    embeddings = model.encode(queries, convert_to_numpy=True)
    return jsonify({'embeddings': embeddings.tolist()})

if __name__ == "__main__":
    # Load environment variables right before we need them
    load_dotenv(override=True)  # Add override=True to force reload
    
    # Get file directory from config
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
    
    # Set up file system observer
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, file_directory, recursive=False)
    observer.start()
    print(f"Started watching directory: {file_directory}")

    # Start the server
    serve(app, host='localhost', port=5000, threads=1)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join() 