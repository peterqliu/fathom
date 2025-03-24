import os
import time
import numpy as np
from sklearn.cluster import KMeans
import networkx as nx
from sklearn.metrics.pairwise import paired_distances
import json
import nltk
import argparse
import faiss

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
        model_service: Optional ModelService instance for embeddings
    """
    if not sentences or not isinstance(sentences, list):
        raise ValueError(f"Invalid sentences input. Got type: {type(sentences)}")
    
    print(f"Found {len(sentences)} sentences")
    
    try:
        if model_service is None:
            print("Model service is None!")
            raise ValueError("No model service provided for embeddings")
            
        print(f"Model service state: {model_service.state if hasattr(model_service, 'state') else 'unknown'}")
        print("Attempting to encode sentences...")
        embeddings = model_service.encode(sentences)
        print(f"Embeddings shape: {embeddings.shape if hasattr(embeddings, 'shape') else 'unknown'}")
        
        if embeddings is None or (hasattr(embeddings, 'size') and embeddings.size == 0):
            print("No embeddings were generated!")
            raise ValueError("No embeddings were generated")
            
        # Ensure embeddings are 2D numpy array
        if len(embeddings.shape) == 1:
            print("Reshaping 1D embeddings to 2D")
            embeddings = embeddings.reshape(1, -1)
            
        return embeddings
        
    except Exception as e:
        print(f"Error generating embeddings: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        raise

def auto_kmeans_sentence_selection(sentences, embeddings, indices, filename, proportion=0.1):
    """Dynamically selects number of clusters and finds closest sentences."""
    num_clusters = max(1, round(len(sentences) * proportion))
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

def summarize_text(sentences, pageIndex, filepath, method='kmeans', proportion=0.05, model_service=None):
    """Summarizes text using dynamic K-Means clustering."""
    start_pdf = time.time()
    
    # Get sentence embeddings
    start_embed = time.time()
    embeddings = get_sentence_embeddings(sentences, pageIndex, model_service)
    embed_time = time.time() - start_embed
    sent_per_second = len(sentences) / embed_time

    print(f"Embedding: {embed_time:.2f}s ({sent_per_second:.2f} sent/s)")

    start_summary = time.time()
    if method == "kmeans":
        cluster_info = auto_kmeans_sentence_selection(sentences, embeddings, pageIndex, filepath, proportion)
        summary_time = time.time() - start_summary
    else:
        raise ValueError("Invalid method. Use 'kmeans'")

    sent_per_second_summary = len(sentences) / summary_time
    print("--------------------------------")
    print(f"Summarization: {summary_time:.2f}s ({sent_per_second_summary:.2f} sent/s)")
    
    # Remove direct print of cluster_info and ensure it's properly formatted
    if not isinstance(cluster_info, dict):
        raise ValueError("cluster_info must be a dictionary")
        
    return cluster_info

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description='Summarize a PDF file using K-means clustering.')
#     parser.add_argument('pdf_file', help='Path to the PDF file to summarize')
#     args = parser.parse_args()

#     start_total = time.time()

#     start_pdf = time.time()
#     pdf_data = extract_text_from_pdf(args.pdf_file)
#     sentences = pdf_data['sentences']
#     pageIndex = pdf_data['pageIndex']
#     pdf_time = time.time() - start_pdf
#     chars_per_second_pdf = len(pdf_data['text']) / pdf_time
#     print("--------------------------------")
#     print(f"PDF extraction")
#     print(f"{pdf_time:.2f} seconds, {len(pdf_data['text'])} characters ({chars_per_second_pdf/1000:.2f}k char/s)")
#     print("--------------------------------")

#     input_word_count = len(pdf_data['text'].split())

#     cluster_info = summarize_text(sentences, pageIndex, args.pdf_file, method='kmeans', proportion=0.05)

#     output_word_count = sum(len(sentence.split()) for sentence in cluster_info['sentences'])
#     compression_ratio = output_word_count / input_word_count

#     print(f"K-Means Summary: {cluster_info['count']} clusters from {len(sent_tokenize(pdf_data['text']))} sentences")
#     print(f"Input: {input_word_count} | Output: {output_word_count} | (Compression: {compression_ratio:.2%})")

#     total_time = time.time() - start_total
#     chars_per_second = len(pdf_data['text']) / total_time
#     print("--------------------------------")
#     print(f"Total: {total_time:.2f}s ({len(pdf_data['text'])/1000:.0f}k chars ({chars_per_second/1000:.2f}k char/s)")
#     print("--------------------------------")

#     output_path = os.path.join(os.path.dirname(args.pdf_file), 'kMeans.json')
#     with open(output_path, 'w', encoding='utf-8') as f:
#         json.dump(cluster_info, f, indent=4, ensure_ascii=False) 