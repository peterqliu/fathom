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
        all_clusters['files'].append({
            'path': relative_path,
            'sentences': sentences_dict[file_path],
            'indices': page_indices_dict[file_path],
            'id_start': int(current_id),
            'id_end': int(current_id + num_embeddings)
        })
        
        current_id += num_embeddings
    
    # Combine all embeddings and IDs
    all_embeddings = np.vstack([np.array(e) for e in embeddings_list])
    all_ids = np.concatenate(ids_list)
    
    # Create FAISS index with ID mapping
    dimension = all_embeddings.shape[1]
    base_index = faiss.IndexFlatL2(dimension)
    vector_index = faiss.IndexIDMap(base_index)
    vector_index.add_with_ids(all_embeddings.astype(np.float32), all_ids)
    
    return vector_index, all_clusters

# Gets the appropriate index directory path based on environment
def get_index_dir():
    """Get the appropriate index directory path"""
    if getattr(sys, 'frozen', False):
        # We are running in a bundle
        app_support = os.path.expanduser('~/Library/Application Support/Fathom')
        index_dir = os.path.join(app_support, 'index')
    else:
        # We are running in development
        index_dir = os.path.abspath('index')
    
    # Create directory if it doesn't exist
    os.makedirs(index_dir, exist_ok=True)
    return index_dir

# Recursively indexes all supported files in a directory
def index_directory(directory_path, proportion=0.05, model_service=None):
    """
    Recursively index all supported files (PDF, MOBI, EPUB) in a directory and its subdirectories.
    Creates a combined FAISS index of all cluster centers.
    
    Args:
        directory_path: Path to directory to index
        proportion: Proportion of sentences to use for clustering (default: 0.05)
        model_service: Optional ModelService instance for embeddings
    """
    print(f"Using index directory: {INDEX_DIR}")  # Debug print
    print(f"Indexing directory: {directory_path}")  # Debug print
    
    if not os.path.exists(directory_path):
        print(f"Directory does not exist: {directory_path}")
        return
    
    if not os.path.isdir(directory_path):
        print(f"Path is not a directory: {directory_path}")
        return
    
    # Collect all supported files recursively
    supported_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(('.pdf', '.epub', '.txt', '.doc', '.docx', '.rtf')):
                # Use os.path.join and then os.path.normpath to handle spaces correctly
                file_path = os.path.normpath(os.path.join(root, file))
                supported_files.append(file_path)
    
    if not supported_files:
        print("No supported files found in the directory.")
        return

    print(f"Found {len(supported_files)} supported files")

    # Initialize dictionaries to store results
    sentences_dict = {}
    page_indices_dict = {}
    embeddings_list = []
    file_paths = []
    start_time = time.time()
    
    for supported_file in supported_files:
        try:
            print(f"Processing: {supported_file}")
            
            # Extract text based on file format
            file_extension = os.path.splitext(supported_file)[1].lower()
            try:
                print(f"Processing file: {supported_file} with extension: {file_extension}")  # Debug line
                
                if file_extension == '.pdf':
                    cluster_info = summarize_text(supported_file)
                # elif file_extension == '.epub':
                #     sentences, pageIndex = extract_text_from_epub(supported_file)
                # elif file_extension == '.txt':
                #     sentences, pageIndex = extract_text_from_txt(supported_file)
                # elif file_extension == '.docx':
                #     sentences, pageIndex = extract_text_from_docx(supported_file)
                # elif file_extension == '.rtf':
                #     sentences, pageIndex = extract_text_from_rtf(supported_file)
                # elif file_extension == '.doc':
                #     sentences, pageIndex = extract_text_from_doc(supported_file)
                # elif file_extension == '.mobi':
                #     print(f"Warning: MOBI files need conversion to EPUB first. Skipping {supported_file}")
                #     continue
                else:
                    print(f"Unsupported file format: {file_extension}")
                    continue
                    
                if not cluster_info:
                    print(f"No text extracted from {supported_file}")
                    continue
                    
            except Exception as e:
                print(f"Error processing {supported_file}: {str(e)}")
                print(f"Error type: {type(e).__name__}")  # Debug line
                continue
            
            # Store results with the full file path as the key
            sentences_dict[supported_file] = cluster_info.get('sentences', [])
            page_indices_dict[supported_file] = cluster_info.get('page_indices', [])
            file_paths.append(supported_file)
            
            # Get clusters for this document
            if cluster_info and 'embeddings' in cluster_info:
                embeddings_list.append(cluster_info['embeddings'])
                print(f"Successfully generated embeddings for {supported_file}")
            else:
                print(f"No valid embeddings generated for {supported_file}")
                continue
            
        except Exception as e:
            print(f"Error processing {supported_file}: {str(e)}")
            continue

    if embeddings_list:
        try:
            print("Creating FAISS index...")
            # Create FAISS index with ID mapping
            vector_index, all_clusters = create_faiss_index_with_ids(
                embeddings_list, 
                sentences_dict,
                page_indices_dict,
                file_paths,
                directory_path
            )
            
            print(f"Saving index to {VECTOR_INDEX_FILE}")
            faiss.write_index(vector_index, VECTOR_INDEX_FILE)
            
            print(f"Saving clusters to {CLUSTERS_FILE}")
            with open(CLUSTERS_FILE, 'w') as f:
                json.dump(all_clusters, f, indent=2)
            
            print(f"\nProcessed {len(supported_files)} supported files")
            total_time = time.time() - start_time
            print("--------------------------------")
            print(f"Total indexing time: {total_time:.2f} seconds")
            print("--------------------------------")
            
            # Calculate and log size metrics in one line
            dir_size = get_directory_size(directory_path)
            index_size = os.path.getsize(VECTOR_INDEX_FILE)
            print(blue(f"Sizes: Directory={format_size(dir_size)}, Index={format_size(index_size)} ({(index_size/dir_size)*100:.2f}% of original)"))
            print("--------------------------------")
        except Exception as e:
            print(f"Error saving index files: {str(e)}")
            raise
    else:
        print("No valid embeddings were generated.")

def remove_file_embeddings(filename):
    """
    Remove embeddings for a specific file from the FAISS index and metadata.
    
    Args:
        filename (str): Name of the file to remove (will be matched against relative paths)
    """
    # Get index directory directly (don't use environment variable)
    index_dir = get_index_dir()
    print(f"Using index directory: {index_dir}")  # Debug print
        
    try:
        # Load existing metadata
        with open(os.path.join(index_dir, 'clusters.json'), 'r', encoding='utf-8') as f:
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
        vector_index = faiss.read_index(os.path.join(index_dir, 'vectorIndex'))
        
        # Remove vectors by their IDs
        vector_index.remove_ids(ids_to_remove)
        
        # Update metadata
        all_clusters['files'].pop(file_index)
        
        # Save updated index and metadata
        faiss.write_index(vector_index, os.path.join(index_dir, 'vectorIndex'))
        with open(os.path.join(index_dir, 'clusters.json'), 'w') as f:
            json.dump(all_clusters, f, indent=4, ensure_ascii=False)
        
        print(f"Successfully removed embeddings for {filename}")
        
    except Exception as e:
        print(f"Error removing embeddings: {str(e)}")

def get_target_directory():
    """
    Read and return the target directory from the config file.
    
    Returns:
        str: The target directory path
        
    Raises:
        ValueError: If config file is missing, invalid, or missing targetDirectory
    """
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            directory = config.get('targetDirectory')
            if not directory:
                raise ValueError("targetDirectory not found in config file")
            return os.path.expanduser(directory)  # Expand ~ to home directory
    except FileNotFoundError:
        raise ValueError(f"Config file not found at {CONFIG_FILE}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in config file at {CONFIG_FILE}")

if __name__ == "__main__":

        directory = get_target_directory()
        print("Indexing directory: ", directory)
        index_directory(directory, 0.05) 