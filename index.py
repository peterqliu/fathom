import faiss
import numpy as np
from summarize import summarize_text
from file_utils import get_directory_size, format_size, blue
import json
import time
import os
import sys
from constants import INDEX_DIR, Config # VECTOR_INDEX_FILE removed, will be handled by VectorIndex
from sqlite_utils import init_sqlite_db, get_or_create_file_id, insert_sentences, is_file_already_indexed
from vectorIndex_utils import VectorIndex # Added import
import logging

logger = logging.getLogger(__name__)

# Set tokenizers parallelism before importing any HuggingFace modules
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def process_file_for_indexing(file_path, vector_idx: VectorIndex):
    """
    Process a single file and update the FAISS index using VectorIndex.
    
    Args:
        file_path: Full path to the file to process
        vector_idx: Instance of the VectorIndex class
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    try:
        print(f"Processing: {file_path}")
        
        # Extract text based on file format
        file_extension = os.path.splitext(file_path)[1].lower()
        try:
            if file_extension == '.pdf':
                cluster_info = summarize_text(file_path)
            else:
                print(f"Unsupported file format: {file_extension}")
                return False
                
            if not cluster_info:
                print(f"No text extracted from {file_path}")
                return False
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            return False
        
        # Get embeddings for this document
        if cluster_info and 'embeddings' in cluster_info:
            embeddings = np.array(cluster_info['embeddings'])

            
            # Prepare page_and_sub_indices for insert_sentences
            page_indices = cluster_info['indices']
            sub_indices = cluster_info['sub_indices']
            page_and_sub_indices = list(zip(page_indices, sub_indices))
            
            # Get or create file_id for the current file_path
            file_id = get_or_create_file_id(file_path)

            # Pass file_id to insert_sentences instead of file_path
            row_ids = insert_sentences(file_id, page_and_sub_indices)
            
            # Use SQLite row IDs for the vector index
            file_ids_np = np.array(row_ids, dtype=np.int64)
            vector_idx.add_with_ids(embeddings, file_ids_np)
            
            vector_idx.save_index()

            return True
            
        else:
            print(f"No valid embeddings generated for {file_path}")
            return False
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return False

def index_directory(directory_path, proportion=0.05, model_service=None):
    """
    Recursively index all supported files (PDF, MOBI, EPUB) in a directory and its subdirectories.
    Creates and updates a FAISS index incrementally as files are processed using VectorIndex.
    
    Args:
        directory_path: Path to directory to index
        proportion: Proportion of sentences to use for clustering (default: 0.05)
        model_service: Optional ModelService instance for embeddings (currently unused)
    """
    print(f"Using index directory: {INDEX_DIR}") # INDEX_DIR might be different from where vector_idx saves its file
    print(f"Indexing directory: {directory_path}")
    
    # Initialize SQLite database tables
    init_sqlite_db(
        table_name='sentences',
        columns=[
            'rowid INTEGER PRIMARY KEY',
            'file_id integer',
            'id INTEGER',
            'sub_index INTEGER'
        ]
    )

    init_sqlite_db(
        table_name='filenames',
        columns=[
            'file_id INTEGER PRIMARY KEY',
            'path TEXT',
            'lastIndexed INTEGER'
        ]
    )
    
    if not os.path.exists(directory_path):
        print(f"Directory does not exist: {directory_path}")
        return
    
    if not os.path.isdir(directory_path):
        print(f"Path is not a directory: {directory_path}")
        return
    
    # Initialize VectorIndex (will load or create the index file as per its logic)
    vector_idx = VectorIndex() # Uses VECTOR_INDEX_FILE from constants by default
    
    # Collect all supported files recursively
    supported_files = []
    files_to_process = []
    skipped_count = 0
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(('.pdf', '.epub', '.txt', '.doc', '.docx', '.rtf')):
                file_path = os.path.normpath(os.path.join(root, file))
                supported_files.append(file_path)
                
                # Check if file is already indexed and up-to-date
                if is_file_already_indexed(file_path):
                    skipped_count += 1
                else:
                    files_to_process.append(file_path)
    
    if not supported_files:
        print("No files found to index.")
        return
        
    if not files_to_process:
        print(f"Found {len(supported_files)} files, all are already up-to-date.")
        return

    print(f"Found {len(supported_files)} files: {len(files_to_process)} need processing, {skipped_count} are up-to-date")
    start_time = time.time()
    processed_count = 0
    
    for file_path in files_to_process:
        # Process the file and update index
        success = process_file_for_indexing(
            file_path, vector_idx
        )
        
        if success:
            # Save index after each successful file processing
            print(f"Saving index after processing {file_path}")
            processed_count += 1
    
    if processed_count > 0:
        total_time = time.time() - start_time
        print("--------------------------------")
        print(f"Total indexing time: {total_time:.2f} seconds")
        print(f"Processed {processed_count} new files, skipped {skipped_count} up-to-date files")
        print("--------------------------------")
        
        # Calculate and log size metrics
        dir_size = get_directory_size(directory_path)
        # Ensure index file path used by VectorIndex is used for size calculation
        index_file_path_used = vector_idx.index_file_path 
        if os.path.exists(index_file_path_used):
            index_size = os.path.getsize(index_file_path_used)
            percentage_of_original = (index_size / dir_size * 100) if dir_size > 0 else 0.00
            print(blue(f"Sizes: Directory={format_size(dir_size)}, Index={format_size(index_size)} ({percentage_of_original:.2f}% of original)"))
        else:
            print(blue(f"Sizes: Directory={format_size(dir_size)}, Index file not found at {index_file_path_used}"))
        print("--------------------------------")
    else:
        print("No new files were successfully indexed.")

if __name__ == "__main__":
    directory = Config.getTargetDirectory()
    print("Indexing directory: ", directory)
    index_directory(directory, 0.05) 