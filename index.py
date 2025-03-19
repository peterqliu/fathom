import argparse
import faiss
import numpy as np
from summarize import summarize_text
from pdf_utils import extract_text_from_pdf
from file_utils import get_directory_size, format_size, blue
import json
import time
from dotenv import load_dotenv

# Set tokenizers parallelism before importing any HuggingFace modules

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def create_faiss_index_with_ids(embeddings_list, pdf_files, sentences_dict, indices_dict, directory_path):
    """
    Create a FAISS index with ID mapping for the embeddings.
    
    Args:
        embeddings_list (list): List of embeddings for each PDF file
        pdf_files (list): List of PDF file paths
        sentences_dict (dict): Dictionary mapping file paths to their sentences
        indices_dict (dict): Dictionary mapping file paths to their indices
        directory_path (str): Base directory path for creating relative paths
        
    Returns:
        tuple: (vector_index, all_clusters) where vector_index is the FAISS index
               and all_clusters is the metadata dictionary
    """
    all_clusters = {'files': []}
    ids_list = []
    current_id = 0
    
    # Process embeddings and create metadata
    for embeddings, pdf_file in zip(embeddings_list, pdf_files):
        num_embeddings = len(embeddings)
        file_ids = np.arange(current_id, current_id + num_embeddings, dtype=np.int64)
        ids_list.append(file_ids)
        
        # Store file information with ID range
        relative_path = os.path.relpath(pdf_file, directory_path)
        all_clusters['files'].append({
            'path': relative_path,
            'sentences': sentences_dict[pdf_file],
            'indices': indices_dict[pdf_file],
            'id_start': int(current_id),
            'id_end': int(current_id + num_embeddings)
        })
        
        current_id += num_embeddings
    
    # Combine all embeddings and IDs
    all_embeddings = np.vstack(embeddings_list)
    all_ids = np.concatenate(ids_list)
    
    # Create FAISS index with ID mapping
    dimension = all_embeddings.shape[1]
    base_index = faiss.IndexFlatL2(dimension)
    vector_index = faiss.IndexIDMap(base_index)
    vector_index.add_with_ids(all_embeddings, all_ids)
    
    return vector_index, all_clusters

def index_directory(directory_path, proportion=0.05):
    """
    Recursively index all PDF files in a directory and its subdirectories.
    Creates a combined FAISS index of all cluster centers.
    """
    # Collect all PDF files recursively
    pdf_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    if not pdf_files:
        print("No PDF files found in the directory.")
        return

    # Process each PDF file
    embeddings_list = []
    sentences_dict = {}  # Store sentences for metadata
    indices_dict = {}    # Store indices for metadata
    start_time = time.time()
    
    for pdf_file in pdf_files:
        try:
            print(f"Processing: {pdf_file}")
            
            # Extract text from PDF
            sentences, pageIndex = extract_text_from_pdf(pdf_file)
            # Get clusters for this document
            cluster_info = summarize_text(sentences, pageIndex, pdf_file, method='kmeans', proportion=proportion)
            embeddings_list.append(cluster_info['embeddings'])
            sentences_dict[pdf_file] = cluster_info['sentences']
            indices_dict[pdf_file] = cluster_info['indices']
            
        except Exception as e:
            print(f"Error processing {pdf_file}: {str(e)}")
            continue

    if embeddings_list:
        # Create FAISS index with ID mapping
        vector_index, all_clusters = create_faiss_index_with_ids(
            embeddings_list, 
            pdf_files, 
            sentences_dict,
            indices_dict,
            directory_path
        )
        
        # Save the combined index
        faiss.write_index(vector_index, 'vectorIndex')
        
        # Save the cluster information
        with open('directory_clusters.json', 'w', encoding='utf-8') as f:
            json.dump(all_clusters, f, indent=4, ensure_ascii=False)
        
        print(f"\nProcessed {len(pdf_files)} PDF files")
        total_time = time.time() - start_time
        print("--------------------------------")
        print(f"Total indexing time: {total_time:.2f} seconds")
        print("--------------------------------")
        
        # Calculate and log size metrics in one line
        dir_size = get_directory_size(directory_path)
        index_size = os.path.getsize('vectorIndex')
        print(blue(f"Sizes: Directory={format_size(dir_size)}, Index={format_size(index_size)} ({(index_size/dir_size)*100:.2f}% of original)"))
        print("--------------------------------")
    else:
        print("No valid embeddings were generated.")

def remove_file_embeddings(filename):
    """
    Remove embeddings for a specific file from the FAISS index and metadata.
    
    Args:
        filename (str): Name of the file to remove (will be matched against relative paths)
    """
    try:
        # Load existing metadata
        with open('directory_clusters.json', 'r', encoding='utf-8') as f:
            all_clusters = json.load(f)
        
        # Find the file and its ID range in metadata
        file_index = None
        for i, file_info in enumerate(all_clusters['files']):
            if filename in file_info['path']:
                file_index = i
                break
        
        if file_index is None:
            print(f"File {filename} not found in metadata")
            return
        
        # Get the ID range to remove
        file_info = all_clusters['files'][file_index]
        ids_to_remove = np.arange(file_info['id_start'], file_info['id_end'], dtype=np.int64)
        
        # Load the FAISS index
        vector_index = faiss.read_index('vectorIndex')
        
        # Remove vectors by their IDs
        vector_index.remove_ids(ids_to_remove)
        
        # Update metadata
        all_clusters['files'].pop(file_index)
        
        # Save updated index and metadata
        faiss.write_index(vector_index, 'vectorIndex')
        with open('directory_clusters.json', 'w', encoding='utf-8') as f:
            json.dump(all_clusters, f, indent=4, ensure_ascii=False)
        
        print(f"Successfully removed embeddings for {filename}")
        
    except Exception as e:
        print(f"Error removing embeddings: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Index all PDF files in a directory using K-means clustering.')
    parser.add_argument('--proportion', type=float, default=0.05,
                        help='Proportion of sentences to use for clustering (default: 0.05)')
    parser.add_argument('--remove', type=str,
                        help='Remove embeddings for a specific file (provide filename or path)')
    
    args = parser.parse_args()
    load_dotenv()  # Load environment variables from .env file
    
    if args.remove:
        print(f"Removing embeddings for: {args.remove}")
        remove_file_embeddings(args.remove)
    else:
        directory = os.getenv('FILE_DIRECTORY')
        print("Indexing directory: ", directory)
        index_directory(directory, args.proportion) 