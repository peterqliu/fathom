import argparse
import faiss
import numpy as np
from summarize import summarize_text
from file_utils import get_directory_size, format_size, blue
import json
import time
import os
import sys
from constants import INDEX_DIR, VECTOR_INDEX_FILE, SQLITE_DB_FILE
from utilities import get_index_dir, get_target_directory
from utils.model_wrapper import ModelServiceWrapper
from sqlite_utils import init_sqlite_db, insert_sentences, init_filenames_table,  get_sentence_by_id
from parsers.pdf_utils import extract_text_from_pdf_page
from PyPDF2 import PdfReader
import logging

logger = logging.getLogger(__name__)

# Set tokenizers parallelism before importing any HuggingFace modules
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def process_file_for_indexing(file_path, directory_path, vector_index):
    """
    Process a single file and update the FAISS index.
    
    Args:
        file_path: Full path to the file to process
        directory_path: Base directory path for creating relative paths
        vector_index: Existing FAISS index or None if new
        
    Returns:
        tuple: (updated_vector_index, success) where success is a boolean indicating if processing was successful
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
                return vector_index, False
                
            if not cluster_info:
                print(f"No text extracted from {file_path}")
                return vector_index, False
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            return vector_index, False
        
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
            
            # Insert sentences into SQLite database and get row IDs
            relative_path = os.path.relpath(file_path, directory_path)
            row_ids = insert_sentences(file_path, cluster_info['sentences'], cluster_info['indices'])
            
            # Use SQLite row IDs for the vector index
            file_ids = np.array(row_ids, dtype=np.int64)
            vector_index.add_with_ids(embeddings.astype(np.float32), file_ids)
            
            print(f"Successfully processed {file_path}")
            return vector_index, True
            
        else:
            print(f"No valid embeddings generated for {file_path}")
            return vector_index, False
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return vector_index, False

def index_directory(directory_path, proportion=0.05, model_service=None):
    """
    Recursively index all supported files (PDF, MOBI, EPUB) in a directory and its subdirectories.
    Creates and updates a FAISS index incrementally as files are processed.
    
    Args:
        directory_path: Path to directory to index
        proportion: Proportion of sentences to use for clustering (default: 0.05)
        model_service: Optional ModelService instance for embeddings
    """
    print(f"Using index directory: {INDEX_DIR}")
    print(f"Indexing directory: {directory_path}")
    
    # Initialize SQLite database tables
    init_sqlite_db(
        table_name='sentences',
        columns=[
            'rowid INTEGER PRIMARY KEY',
            'path TEXT',
            'sentence TEXT',
            'id INTEGER'
        ]
    )
    init_filenames_table()
    
    if not os.path.exists(directory_path):
        print(f"Directory does not exist: {directory_path}")
        return
    
    if not os.path.isdir(directory_path):
        print(f"Path is not a directory: {directory_path}")
        return
    
    # Initialize or load existing index
    try:
        if os.path.exists(VECTOR_INDEX_FILE):
            print("Loading existing FAISS index...")
            vector_index = faiss.read_index(VECTOR_INDEX_FILE)
        else:
            print("Creating new FAISS index...")
            vector_index = None
    except Exception as e:
        print(f"Error loading existing index: {str(e)}")
        print("Creating new index...")
        vector_index = None
    
    # Collect all supported files recursively
    supported_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(('.pdf', '.epub', '.txt', '.doc', '.docx', '.rtf')):
                file_path = os.path.normpath(os.path.join(root, file))
                supported_files.append(file_path)
    
    if not supported_files:
        print("No new files to index.")
        return

    print(f"Found {len(supported_files)} new files to index")
    start_time = time.time()
    processed_count = 0
    
    for supported_file in supported_files:
        # Process the file and update index
        vector_index, success = process_file_for_indexing(
            supported_file, directory_path, vector_index
        )
        
        if success:
            # Save index after each successful file processing
            print(f"Saving index after processing {supported_file}")
            faiss.write_index(vector_index, VECTOR_INDEX_FILE)
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