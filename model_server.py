from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
from waitress import serve
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)

# Define model cache directory
model_name = 'BAAI/bge-large-en'
cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_cache")

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
model.encode(["warmup"])  # Warmup encoding to ensure model is loaded
print("Model loaded and ready!")

# File system event handler
class FileChangeHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"File created: {event.src_path}")
            print('--------------------------------')

    def on_deleted(self, event):
        if not event.is_directory:
            print(f"File deleted: {event.src_path}")
            print('--------------------------------')
            
    def on_moved(self, event):
        print('event', event)
        if not event.is_directory:
            print(f"File renamed/moved:")
            print(f"  from: {event.src_path}")
            print(f"  to: {event.dest_path}")
            print('--------------------------------')

@app.route('/encode', methods=['POST'])
def encode():
    data = request.json
    query = data['query']
    embedding = model.encode([query], convert_to_numpy=True)
    return jsonify({'embedding': embedding.tolist()})

if __name__ == "__main__":
    # Load environment variables right before we need them
    load_dotenv(override=True)  # Add override=True to force reload
    file_directory = os.getenv('FILE_DIRECTORY')
    
    # Set up file system observer
    if file_directory:
        event_handler = FileChangeHandler()
        observer = Observer()
        observer.schedule(event_handler, file_directory, recursive=False)
        observer.start()
        print(f"Started watching directory: {file_directory}")
    else:
        print("FILE_DIRECTORY environment variable not set")

    # Start the server
    serve(app, host='localhost', port=5000, threads=1)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if file_directory:
            observer.stop()
            observer.join() 