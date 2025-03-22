import faiss
import json
import numpy as np
import argparse
import requests
from parsers.text_utils import (
    extract_text_from_txt,
    extract_text_from_docx,
    extract_text_from_rtf,
    extract_text_from_doc
)
from parsers.pdf_utils import extract_text_from_pdf_page
from parsers.ebook_utils import extract_text_from_epub
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv(override=True)
directory = os.getenv('FILE_DIRECTORY')
print('DIRECTORY', directory)
if not os.getenv('INDEX_DIRECTORY'):
    raise ValueError("INDEX_DIRECTORY environment variable not set")

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def search_index(query, top_k=5, model_service=None):
    """
    Search the vector index for similar sentences to the query.
    Returns the top_k most similar sentences with their metadata.
    
    Args:
        query: Query string or embedding
        top_k: Number of results to return
        model_service: Optional ModelService instance. If None, uses localhost HTTP endpoint
    """
    # Load the FAISS index
    try:
        vector_index = faiss.read_index(get_resource_path('index/vectorIndex'))
    except Exception as e:
        raise RuntimeError(f"Failed to load vector index: {str(e)}")

    # Load the clusters metadata
    try:
        with open(get_resource_path('index/clusters.json'), 'r', encoding='utf-8') as f:
            clusters_data = json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load clusters data: {str(e)}")

    # Get query embedding either from model service or local server
    if model_service is not None:
        query_embedding = model_service.encode(query)
    else:
        # Fallback to HTTP endpoint for CLI usage
        response = requests.post('http://localhost:5000/encode', json={'query': query})
        query_embedding = np.array(response.json()['embedding'])
    
    # Search the index
    distances, indices = vector_index.search(query_embedding.astype(np.float32), top_k)
    
    # Collect results
    results = []
    current_idx = 0
    
    for file_data in clusters_data['files']:
        num_clusters = len(file_data['sentences'])
        file_indices = indices[0][(indices[0] >= current_idx) & (indices[0] < current_idx + num_clusters)]
        
        if len(file_indices) > 0:
            for idx in file_indices:
                relative_idx = idx - current_idx
                results.append({
                    'file': file_data['path'],
                    'sentence': file_data['sentences'][relative_idx],
                    'indices': file_data['indices'][relative_idx],
                    'distance': float(distances[0][np.where(indices[0] == idx)[0][0]])
                })
        
        current_idx += num_clusters
    
    # Sort results by distance
    results.sort(key=lambda x: x['distance'])
    return results[:top_k]

def extract_page_from_file(filepath, indices):
    """
    Extract text from a specific page/section of a file based on its format.
    """
    if isinstance(indices, int):
        indices = [indices]
    
    file_extension = os.path.splitext(filepath)[1].lower()
    
    # Map file extensions to their extraction functions
    extractors = {
        '.pdf': lambda f: (PdfReader(f), extract_text_from_pdf_page),
        '.txt': extract_text_from_txt,
        '.docx': extract_text_from_docx,
        '.doc': extract_text_from_doc,
        '.rtf': extract_text_from_rtf,
        '.epub': extract_text_from_epub
    }
    
    try:
        if file_extension not in extractors:
            raise ValueError(f"Unsupported file format: {file_extension}")
            
        extractor = extractors[file_extension]
        
        # Special handling for PDF since it has a different return format
        if file_extension == '.pdf':
            reader, extract_func = extractor(filepath)
            return extract_func(reader, indices)
        
        # Handle all other formats that return (sentences, page_indices)
        sentences, page_indices = extractor(filepath)
        relevant_sentences = [s for i, s in enumerate(sentences) if page_indices[i] in indices]
        return ' '.join(relevant_sentences)
            
    except Exception as e:
        print(f"Error extracting text from {filepath}: {str(e)}")
        return ""

def print_context(file_path, indices, sentence):
    """
    Print the context from the file for the given indices and highlight the sentence.
    """
    page_text = extract_page_from_file(file_path, indices)
    if page_text:
        # Highlight the sentence in the context
        highlighted_text = page_text.replace(sentence, f"\033[93m{sentence}\033[0m")
        print(highlighted_text)
    else:
        print("Could not extract context from file.")
    print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Search indexed PDF files using a query.')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--top_k', type=int, default=5,
                        help='Number of results to return (default: 5)')
    
    args = parser.parse_args()
    
    try:
        results = search_index(args.query, args.top_k)

        print(f"\nTop {args.top_k} matches for query: '{args.query}'\n")

        for i, result in enumerate(results, 1):
            file, indices, distance, sentence = result['file'], result['indices'], result['distance'], result['sentence']
            print(f"{i}. File: {file}")
            print(f"   Index: {indices}")
            print(f"   Distance: {distance:.4f}")
            print(f"   Text: {sentence}\n")

            file_path = os.path.join(directory, file)
            print_context(file_path, indices, sentence)
            print()
    except Exception as e:
        print(f"Error: {str(e)}") 