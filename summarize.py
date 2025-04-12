import os
import time
import numpy as np
from sklearn.cluster import KMeans
import networkx as nx
from sklearn.metrics.pairwise import paired_distances
import json
import nltk
from nltk.tokenize import sent_tokenize
import argparse
import faiss
from parsers.pdf_utils import stream_text_from_pdf
import requests
from constants import CLUSTERS_FILE

# Ensure NLTK data is downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def get_sentence_embeddings(sentences, indices, model_service=None):
    """
    Convert sentences into embeddings.
    
    Args:
        sentences (list): List of sentences to embed
        indices (list): List of indices for the sentences
        model_service: Optional ModelService instance for embeddings (ignored, using HTTP endpoint)
    """
    if not sentences or not isinstance(sentences, list):
        raise ValueError(f"Invalid sentences input. Got type: {type(sentences)}")
    
    print(f"Found {len(sentences)} sentences")
    
    try:
        print("Attempting to encode sentences...")
        # Get embeddings for each sentence individually
        embeddings = []
        for sentence in sentences:
            response = requests.post('http://localhost:5000/encode', json={'query': sentence})
            if response.status_code != 200:
                raise ValueError(f"Failed to get embedding: {response.text}")
            embedding = np.array(response.json()['embedding'])

            embeddings.append(embedding)
            
        embeddings = np.array(embeddings)
        print(f"Embeddings shape: {embeddings.shape if hasattr(embeddings, 'shape') else 'unknown'}")
        
        if embeddings is None or (hasattr(embeddings, 'size') and embeddings.size == 0):
            print("No embeddings were generated!")
            raise ValueError("No embeddings were generated")
            
        if embeddings.shape[0] != len(sentences):
            raise ValueError(f"Number of embeddings ({embeddings.shape[0]}) does not match number of sentences ({len(sentences)})")
            
        return embeddings
        
    except Exception as e:
        print(f"Error generating embeddings: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        raise

def process_streaming_pdf(filepath, batch_size=64):
    """
    Process PDF file in streaming fashion, extracting and embedding sentences as they come.
    
    Args:
        filepath (str): Path to the PDF file
        batch_size (int): Number of sentences to batch together for embedding
        
    Returns:
        tuple: (sentences, indices, embeddings) - lists of processed data
    """
    sentences = []
    indices = []
    embeddings = []
    current_batch = []
    current_batch_indices = []
    
    start_time = time.time()
    sentence_count = 0
    
    print("Starting PDF processing...")
    for sentence, page_index in stream_text_from_pdf(filepath):
        current_batch.append(sentence)
        current_batch_indices.append(page_index)
        
        if len(current_batch) >= batch_size:
            # Process the batch
            response = requests.post('http://localhost:5000/encode_batch', 
                                  json={'queries': current_batch})
            if response.status_code != 200:
                raise ValueError(f"Failed to get embeddings: {response.text}")
            
            batch_embeddings = np.array(response.json()['embeddings'])
            
            # Store results
            sentences.extend(current_batch)
            indices.extend(current_batch_indices)
            embeddings.extend(batch_embeddings)
            
            # Clear the batch
            current_batch = []
            current_batch_indices = []
            
            sentence_count += batch_size
            if sentence_count % 100 == 0:
                elapsed = time.time() - start_time
                rate = sentence_count / elapsed
                print(f"Processed {sentence_count} sentences ({rate:.2f} sent/s)")
    
    # Process any remaining sentences in the last batch
    if current_batch:
        response = requests.post('http://localhost:5000/encode_batch', 
                              json={'queries': current_batch})
        if response.status_code != 200:
            raise ValueError(f"Failed to get embeddings: {response.text}")
        
        batch_embeddings = np.array(response.json()['embeddings'])
        
        sentences.extend(current_batch)
        indices.extend(current_batch_indices)
        embeddings.extend(batch_embeddings)
        
        sentence_count += len(current_batch)
    
    embeddings = np.array(embeddings)
    elapsed = time.time() - start_time
    print(f"Completed processing {sentence_count} sentences in {elapsed:.2f}s ({sentence_count/elapsed:.2f} sent/s)")
    
    return sentences, indices, embeddings

def auto_kmeans_sentence_selection(sentences, embeddings, indices, filename, proportion=0.1):
    """Dynamically selects number of clusters and finds closest sentences."""
    num_clusters = max(1, round(len(sentences) * proportion))
    print(f"num_clusters: {num_clusters}")
    
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    kmeans.fit(embeddings)

    cluster_centers = kmeans.cluster_centers_
    cluster_info = {
        'count': num_clusters,
        'file': filename,
        'sentences': [],
        'indices': [],
        'embeddings': []
    }

    for i, center in enumerate(cluster_centers):
        distances = paired_distances(embeddings, [center] * len(embeddings))
        closest_idx = np.argmin(distances)
        cluster_info['sentences'].append(sentences[closest_idx])
        cluster_info['indices'].append(indices[closest_idx])
        cluster_info['embeddings'].append(embeddings[closest_idx].tolist())
    
    return cluster_info

def summarize_text(filepath, method='kmeans', proportion=0.05):

    start_total = time.time()

    # Process PDF in streaming fashion
    sentences, pageIndex, embeddings = process_streaming_pdf(filepath)
    input_sentence_count = len(sentences)

    print("--------------------------------")
    print(f"PDF extraction and embedding complete")
    print(f"Processed {input_sentence_count} sentences")
    print("--------------------------------")

    """Summarizes text using dynamic K-Means clustering."""
    start_summary = time.time()
    
    if method == "kmeans":
        cluster_info = auto_kmeans_sentence_selection(sentences, embeddings, pageIndex, filepath, proportion)
        summary_time = time.time() - start_summary
    else:
        raise ValueError("Invalid method. Use 'kmeans'")

    sent_per_second_summary = len(sentences) / summary_time
    print("--------------------------------")
    print(f"Summarization: {summary_time:.2f}s ({sent_per_second_summary:.2f} sent/s)")
    
    if not isinstance(cluster_info, dict):
        raise ValueError("cluster_info must be a dictionary")
        
    output_sentence_count = len(cluster_info['sentences'])
    compression_ratio = output_sentence_count / input_sentence_count

    print(f"K-Means Summary: {cluster_info['count']} clusters from {input_sentence_count} sentences")
    print(f"Input: {input_sentence_count} | Output: {output_sentence_count} | (Compression: {compression_ratio:.2%})")

    total_time = time.time() - start_total
    sentences_per_second = len(sentences) / total_time
    print("--------------------------------")
    print(f"Total: {total_time:.2f}s ({len(sentences)/1000:.0f}k sentences ({sentences_per_second/1000:.2f}k sent/s)")
    print("--------------------------------")

    return cluster_info

if __name__ == "__main__":

    pdf_file = '/Users/peterliu/Documents/Repos/fathom/test/fan.pdf'

    # Run clustering on the accumulated results
    cluster_info = summarize_text(pdf_file, method='kmeans', proportion=0.05)


    # Save to clusters file from constants
    with open(CLUSTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(cluster_info, f, indent=4, ensure_ascii=False) 