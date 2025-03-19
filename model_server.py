from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
from waitress import serve
import os

# Initialize Flask app
app = Flask(__name__)

# Define model cache directory
model_name = 'BAAI/bge-small-en'
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
print("Loading model from cache...")
model = SentenceTransformer(os.path.join(cache_dir, model_name.split('/')[-1]))
model.encode(["warmup"])  # Warmup encoding to ensure model is loaded
print("Model loaded and ready!")

@app.route('/encode', methods=['POST'])
def encode():
    data = request.json
    query = data['query']
    embedding = model.encode([query], convert_to_numpy=True)
    return jsonify({'embedding': embedding.tolist()})

if __name__ == "__main__":
    serve(app, host='localhost', port=5000, threads=1) 