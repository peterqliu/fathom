import argparse
import faiss
import numpy as np
from summarize import summarize_text
# from parsers.pdf_utils import process_streaming_pdf
# from parsers.ebook_utils import extract_text_from_epub, extract_text_from_mobi
from file_utils import get_directory_size, format_size, blue
import json
import time
import os
# from parsers.text_utils import (
#     extract_text_from_txt,
#     extract_text_from_docx,
#     extract_text_from_rtf,
#     extract_text_from_doc
# )
import sys
from constants import INDEX_DIR, VECTOR_INDEX_FILE, CLUSTERS_FILE, CONFIG_FILE
from utils import get_index_dir, get_target_directory

# Set tokenizers parallelism before importing any HuggingFace modules
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Creates a FAISS index with ID mapping for embeddings
def create_faiss_index_with_ids(embeddings_list, sentences_dict, page_indices_dict, file_paths, directory_path):
    """
    Create a FAISS index with ID mapping for the embeddings.
    
    Args:
        embeddings_list (list): List of embeddings for each PDF file
        sentences_dict (dict): Dictionary mapping file paths to their sentences
        page_indices_dict (dict): Dictionary mapping file paths to their page indices
        file_paths (list): List of file paths
        directory_path (str): Base directory path for creating relative paths
        
    Returns:
        tuple: (vector_index, all_clusters) where vector_index is the FAISS index
               and all_clusters is the metadata dictionary
    """
    all_clusters = {'files': []}
    ids_list = []
    current_id = 0
    
    # Process embeddings and create metadata
    for embeddings, file_path in zip(embeddings_list, file_paths):
        # Convert embeddings to numpy array if needed
        if not isinstance(embeddings, np.ndarray):
            embeddings = np.array(embeddings)
        
        # Ensure embeddings are 2D
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
            
        num_embeddings = len(embeddings)
        file_ids = np.arange(current_id, current_id + num_embeddings, dtype=np.int64)
        ids_list.append(file_ids)
        
        # Store file information with ID range
        relative_path = os.path.relpath(file_path, directory_path)
        print(page_indices_dict[file_path])
        all_clusters['files'].append({
            'path': relative_path,
            'sentences': sentences_dict[file_path],
            'indices': page_indices_dict[file_path],
            # 'id_start': int(current_id),
            # 'id_end': int(current_id + num_embeddings)
        })
        
        # current_id += num_embeddings
    
    # Combine all embeddings and IDs
    all_embeddings = np.vstack([np.array(e) for e in embeddings_list])
    all_ids = np.concatenate(ids_list)
    
    # Create FAISS index with ID mapping
    dimension = all_embeddings.shape[1]
    base_index = faiss.IndexFlatL2(dimension)
    vector_index = faiss.IndexIDMap(base_index)
    vector_index.add_with_ids(all_embeddings.astype(np.float32), all_ids)
    
    return vector_index, all_clusters

def process_file_for_indexing(file_path, directory_path, vector_index, all_clusters, current_id):
    """
    Process a single file and update the FAISS index and clusters.
    
    Args:
        file_path: Full path to the file to process
        directory_path: Base directory path for creating relative paths
        vector_index: Existing FAISS index or None if new
        all_clusters: Existing clusters metadata
        current_id: Current ID counter for embeddings
        
    Returns:
        tuple: (updated_vector_index, updated_clusters, new_current_id, success)
               where success is a boolean indicating if processing was successful
    """
    try:
        print(f"Processing: {file_path}")
        
        # Extract text based on file format
        file_extension = os.path.splitext(file_path)[1].lower()
        try:
            print(f"Processing file: {file_path} with extension: {file_extension}")
            
            if file_extension == '.pdf':
                cluster_info = summarize_text(file_path)
            else:
                print(f"Unsupported file format: {file_extension}")
                return vector_index, all_clusters, current_id, False
                
            if not cluster_info:
                print(f"No text extracted from {file_path}")
                return vector_index, all_clusters, current_id, False
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            return vector_index, all_clusters, current_id, False
        
        # Get embeddings for this document
        if cluster_info and 'embeddings' in cluster_info:
            embeddings = np.array(cluster_info['embeddings'])
            if len(embeddings.shape) == 1:
                embeddings = embeddings.reshape(1, -1)
            
            # Initialize or update FAISS index
            if vector_index is None:
                dimension = embeddings.shape[1]
                base_index = faiss.IndexFlatL2(dimension)
                vector_index = faiss.IndexIDMap(base_index)
            
            # Add embeddings to index with IDs
            num_embeddings = len(embeddings)
            file_ids = np.arange(current_id, current_id + num_embeddings, dtype=np.int64)
            vector_index.add_with_ids(embeddings.astype(np.float32), file_ids)
            
            # Update clusters metadata
            relative_path = os.path.relpath(file_path, directory_path)
            all_clusters['files'].append({
                'path': relative_path,
                'sentences': cluster_info['sentences'],
                'indices': cluster_info['indices'],
                # 'id_start': int(current_id),
                # 'id_end': int(current_id + num_embeddings)
            })
            
            current_id += num_embeddings
            print(f"Successfully processed {file_path}")
            return vector_index, all_clusters, current_id, True
            
        else:
            print(f"No valid embeddings generated for {file_path}")
            return vector_index, all_clusters, current_id, False
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return vector_index, all_clusters, current_id, False

def index_directory(directory_path, proportion=0.05, model_service=None):
    """
    Recursively index all supported files (PDF, MOBI, EPUB) in a directory and its subdirectories.
    Creates and updates a FAISS index and clusters incrementally as files are processed.
    
    Args:
        directory_path: Path to directory to index
        proportion: Proportion of sentences to use for clustering (default: 0.05)
        model_service: Optional ModelService instance for embeddings
    """
    print(f"Using index directory: {INDEX_DIR}")
    print(f"Indexing directory: {directory_path}")
    
    if not os.path.exists(directory_path):
        print(f"Directory does not exist: {directory_path}")
        return
    
    if not os.path.isdir(directory_path):
        print(f"Path is not a directory: {directory_path}")
        return
    
    # Initialize or load existing index and clusters
    try:
        if os.path.exists(VECTOR_INDEX_FILE):
            print("Loading existing FAISS index...")
            vector_index = faiss.read_index(VECTOR_INDEX_FILE)
            with open(CLUSTERS_FILE, 'r') as f:
                all_clusters = json.load(f)
            current_id = max([file_info['id_end'] for file_info in all_clusters['files']]) if all_clusters['files'] else 0
        else:
            print("Creating new FAISS index...")
            # Initialize with dummy dimension, will be updated with first file
            vector_index = None
            all_clusters = {'files': []}
            current_id = 0
    except Exception as e:
        print(f"Error loading existing index: {str(e)}")
        print("Creating new index...")
        vector_index = None
        all_clusters = {'files': []}
        current_id = 0
    
    # Collect all supported files recursively
    supported_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(('.pdf', '.epub', '.txt', '.doc', '.docx', '.rtf')):
                file_path = os.path.normpath(os.path.join(root, file))
                # Skip if file is already indexed
                if any(file_info['path'] == os.path.relpath(file_path, directory_path) for file_info in all_clusters['files']):
                    print(f"Skipping already indexed file: {file_path}")
                    continue
                supported_files.append(file_path)
    
    if not supported_files:
        print("No new files to index.")
        return

    print(f"Found {len(supported_files)} new files to index")
    start_time = time.time()
    processed_count = 0
    
    for supported_file in supported_files:
        # Process the file and update index and clusters
        vector_index, all_clusters, current_id, success = process_file_for_indexing(
            supported_file, directory_path, vector_index, all_clusters, current_id
        )
        
        if success:
            # Save index and clusters after each successful file processing
            print(f"Saving index and clusters after processing {supported_file}")
            faiss.write_index(vector_index, VECTOR_INDEX_FILE)
            with open(CLUSTERS_FILE, 'w') as f:
                json.dump(all_clusters, f, indent=2)
            processed_count += 1
    
    if processed_count > 0:
        total_time = time.time() - start_time
        print("--------------------------------")
        print(f"Total indexing time: {total_time:.2f} seconds")
        print(f"Processed {processed_count} new files")
        print("--------------------------------")
        
        # Calculate and log size metrics
        dir_size = get_directory_size(directory_path)
        index_size = os.path.getsize(VECTOR_INDEX_FILE)
        print(blue(f"Sizes: Directory={format_size(dir_size)}, Index={format_size(index_size)} ({(index_size/dir_size)*100:.2f}% of original)"))
        print("--------------------------------")
    else:
        print("No new files were successfully indexed.")

if __name__ == "__main__":
    directory = get_target_directory()
    print("Indexing directory: ", directory)
    index_directory(directory, 0.05) 