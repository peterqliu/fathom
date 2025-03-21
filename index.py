import argparse
import faiss
import numpy as np
from summarize import summarize_text
from parsers.pdf_utils import extract_text_from_pdf
from parsers.ebook_utils import extract_text_from_epub, extract_text_from_mobi
from file_utils import get_directory_size, format_size, blue
import json
import time
from dotenv import load_dotenv
import os
from parsers.text_utils import (
    extract_text_from_txt,
    extract_text_from_docx,
    extract_text_from_rtf,
    extract_text_from_doc
)

# Set tokenizers parallelism before importing any HuggingFace modules
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Load environment variables
# load_dotenv()
index_dir = os.getenv('INDEX_DIRECTORY')

if not index_dir:
    raise ValueError("INDEX_DIRECTORY environment variable not set")

# Create directory if it doesn't exist
os.makedirs(index_dir, exist_ok=True)

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
    Recursively index all supported files (PDF, MOBI, EPUB) in a directory and its subdirectories.
    Creates a combined FAISS index of all cluster centers.
    """
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
                    sentences, pageIndex = extract_text_from_pdf(supported_file)
                elif file_extension == '.epub':
                    sentences, pageIndex = extract_text_from_epub(supported_file)
                elif file_extension == '.txt':
                    sentences, pageIndex = extract_text_from_txt(supported_file)
                elif file_extension == '.docx':
                    sentences, pageIndex = extract_text_from_docx(supported_file)
                elif file_extension == '.rtf':
                    sentences, pageIndex = extract_text_from_rtf(supported_file)
                elif file_extension == '.doc':
                    sentences, pageIndex = extract_text_from_doc(supported_file)
                elif file_extension == '.mobi':
                    print(f"Warning: MOBI files need conversion to EPUB first. Skipping {supported_file}")
                    continue
                else:
                    print(f"Unsupported file format: {file_extension}")
                    continue
            except Exception as e:
                print(f"Error processing {supported_file}: {str(e)}")
                print(f"Error type: {type(e).__name__}")  # Debug line
                continue
            
            # Store results with the full file path as the key
            sentences_dict[supported_file] = sentences
            page_indices_dict[supported_file] = pageIndex
            file_paths.append(supported_file)
            
            # Get clusters for this document
            cluster_info = summarize_text(sentences, pageIndex, supported_file, method='kmeans', proportion=proportion)
            embeddings_list.append(cluster_info['embeddings'])
            
        except Exception as e:
            print(f"Error processing {supported_file}: {str(e)}")
            continue

    if embeddings_list:
        # Create FAISS index with ID mapping
        vector_index, all_clusters = create_faiss_index_with_ids(
            embeddings_list, 
            sentences_dict,
            page_indices_dict,
            file_paths,
            directory_path
        )
        
        # Save the index and clusters to the specified directory
        faiss.write_index(vector_index, os.path.join(index_dir, 'vectorIndex'))
        with open(os.path.join(index_dir, 'clusters.json'), 'w') as f:
            json.dump(all_clusters, f)
        
        print(f"\nProcessed {len(supported_files)} supported files")
        total_time = time.time() - start_time
        print("--------------------------------")
        print(f"Total indexing time: {total_time:.2f} seconds")
        print("--------------------------------")
        
        # Calculate and log size metrics in one line
        dir_size = get_directory_size(directory_path)
        index_size = os.path.getsize(os.path.join(index_dir, 'vectorIndex'))
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Index all supported files in a directory using K-means clustering.')
    parser.add_argument('--proportion', type=float, default=0.05,
                        help='Proportion of sentences to use for clustering (default: 0.05)')
    parser.add_argument('--remove', type=str,
                        help='Remove embeddings for a specific file (provide filename or path)')
    
    args = parser.parse_args()
    load_dotenv(override=True)  # Force reload of environment variables
    
    if args.remove:
        print(f"Removing embeddings for: {args.remove}")
        remove_file_embeddings(args.remove)
    else:
        directory = os.getenv('FILE_DIRECTORY')
        print("Indexing directory: ", directory)
        index_directory(directory, args.proportion) 