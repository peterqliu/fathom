import os
import sys
import time
import numpy as np
from sklearn.cluster import KMeans
import networkx as nx
from sklearn.metrics.pairwise import paired_distances
import nltk
from pdf_utils import stream_text_from_pdf

# Add parent directory to path for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from model import EmbeddingModel

# Ensure NLTK data is downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def get_sentence_embeddings(sentences):
    """
    Convert sentences into embeddings.
    
    Args:
        sentences (list): List of sentences to embed
    """
    if not sentences or not isinstance(sentences, list):
        raise ValueError(f"Invalid sentences input. Got type: {type(sentences)}")
    
    print(f"Found {len(sentences)} sentences")
    
    try:
        print("Attempting to encode sentences...")
        # Get embeddings for all sentences at once
        model = EmbeddingModel()  # Will reuse existing instance due to singleton pattern
        # Wait for model to be ready
        while not model.is_ready():
            time.sleep(0.1)
            
        embeddings = model.encode_batch(sentences)
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
        tuple: (sentences, page_indices, sub_indices, embeddings) - lists of processed data
    """
    sentences = []
    page_indices = [] # Renamed from indices for clarity
    sub_indices = []
    embeddings = []
    current_batch_sentences = []
    current_batch_page_indices = []
    current_batch_sub_indices = []
    
    # Initialize embedding model - will reuse existing instance due to singleton pattern
    model = EmbeddingModel()
    # Wait for model to be ready
    while not model.is_ready():
        time.sleep(0.1)
    
    start_time = time.time()
    sentence_count = 0
    
    for sentence, page_idx, sub_idx in stream_text_from_pdf(filepath):
        current_batch_sentences.append(sentence)
        current_batch_page_indices.append(page_idx)
        current_batch_sub_indices.append(sub_idx)
        
        if len(current_batch_sentences) >= batch_size:
            # Process the batch
            batch_embeddings = model.encode_batch(current_batch_sentences)
            
            # Store results
            sentences.extend(current_batch_sentences)
            page_indices.extend(current_batch_page_indices)
            sub_indices.extend(current_batch_sub_indices)
            embeddings.append(batch_embeddings)  # Store the numpy array directly
            
            # Clear the batch
            current_batch_sentences = []
            current_batch_page_indices = []
            current_batch_sub_indices = []
            
            sentence_count += batch_size
            if sentence_count % 100 == 0:
                elapsed = time.time() - start_time
                rate = sentence_count / elapsed
                print(f"Processed {sentence_count} sentences ({rate:.2f} sent/s)")
    
    # Process any remaining sentences in the last batch
    if current_batch_sentences:
        batch_embeddings = model.encode_batch(current_batch_sentences)
        
        sentences.extend(current_batch_sentences)
        page_indices.extend(current_batch_page_indices)
        sub_indices.extend(current_batch_sub_indices)
        embeddings.append(batch_embeddings)  # Store the numpy array directly
        
        sentence_count += len(current_batch_sentences)
    
    # Combine all embeddings into one numpy array
    embeddings = np.vstack(embeddings) if embeddings else np.array([])
    elapsed = time.time() - start_time
    print(f"Completed processing {sentence_count} sentences in {elapsed:.2f}s ({sentence_count/elapsed:.2f} sent/s)")
    
    return sentences, page_indices, sub_indices, embeddings

def auto_kmeans_sentence_selection(sentences, embeddings, page_indices_list, sub_indices_list, filename, proportion=0.1):
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
        'indices': [], # This will store page_indices
        'sub_indices': [], # New list for sub_indices
        'embeddings': []
    }

    for i, center in enumerate(cluster_centers):
        distances = paired_distances(embeddings, [center] * len(embeddings))
        closest_idx = np.argmin(distances)
        cluster_info['sentences'].append(sentences[closest_idx])
        cluster_info['indices'].append(page_indices_list[closest_idx]) # Storing page_index
        cluster_info['sub_indices'].append(sub_indices_list[closest_idx]) # Storing sub_index
        cluster_info['embeddings'].append(embeddings[closest_idx].tolist())
    
    return cluster_info

def summarize_text(filepath, method='kmeans', proportion=0.05):

    start_total = time.time()

    # Process PDF in streaming fashion
    sentences, page_indices, sub_indices, embeddings = process_streaming_pdf(filepath)
    input_sentence_count = len(sentences)

    print("--------------------------------")
    print(f"PDF extraction and embedding complete")
    print(f"Processed {input_sentence_count} sentences")
    print("--------------------------------")

    """Summarizes text using dynamic K-Means clustering."""
    start_summary = time.time()
    
    if method == "kmeans":
        cluster_info = auto_kmeans_sentence_selection(sentences, embeddings, page_indices, sub_indices, filepath, proportion)
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

# if __name__ == "__main__":

#     pdf_file = '/Users/peterliu/Documents/Repos/fathom/test/fan.pdf'

#     # Run clustering on the accumulated results
#     cluster_info = summarize_text(pdf_file, method='kmeans', proportion=0.05)
#     print(cluster_info)


