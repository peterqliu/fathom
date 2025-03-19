import faiss
import json
import numpy as np
import argparse
import requests
from pdf_utils import extract_text_from_pdf_page
from pypdf import PdfReader
from dotenv import load_dotenv
import os


def search_index(query, top_k=5):
    """
    Search the vector index for similar sentences to the query.
    Returns the top_k most similar sentences with their metadata.
    """
    # Load the FAISS index
    try:
        vector_index = faiss.read_index('vectorIndex')
    except Exception as e:
        raise RuntimeError(f"Failed to load vector index: {str(e)}")

    # Load the clusters metadata
    try:
        with open('directory_clusters.json', 'r', encoding='utf-8') as f:
            clusters_data = json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load clusters data: {str(e)}")

    # Get query embedding from local server
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

def print_context(page, sentence):
    """
    Print context around a sentence if found in page array, otherwise print last line.
    Args:
        page (list): Array of strings containing page text
        sentence (str): Target sentence to find
    """
    try:
        sentence_idx = next(i for i, text in enumerate(page) if sentence in text)
        start_idx = max(0, sentence_idx - 2)
        end_idx = min(len(page), sentence_idx + 3)
        context = page[start_idx:end_idx]
        print("   Context:")
        for line in context:
            print(f"      {line}")
    except StopIteration:
        print(f"   Last line: {page[-1] if page else 'No text found'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Search indexed PDF files using a query.')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--top_k', type=int, default=5,
                        help='Number of results to return (default: 5)')
    
    args = parser.parse_args()
    
    try:
        results = search_index(args.query, args.top_k)
        load_dotenv()  # Load environment variables from .env file
        directory = os.getenv('FILE_DIRECTORY')
        print(f"\nTop {args.top_k} matches for query: '{args.query}'\n")

        for i, result in enumerate(results, 1):
            file, indices, distance, sentence = result['file'], result['indices'], result['distance'], result['sentence']
            print(f"{i}. File: {file}")
            print(f"   Index: {indices}")
            print(f"   Distance: {distance:.4f}")
            print(f"   Text: {sentence}\n")

            reader = PdfReader(os.path.join(directory, file))
            page = extract_text_from_pdf_page(reader, indices)
            print_context(page, sentence)
            print()
    except Exception as e:
        print(f"Error: {str(e)}") 