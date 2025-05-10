import faiss
import numpy as np
import argparse
import requests
import sqlite3
from pdf_utils import extract_text_from_pdf_page, get_sentence_by_indices
import os
import sys
import time
from file_utils import green
# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from constants import INDEX_DIR, VECTOR_INDEX_FILE, SQLITE_DB_FILE, Config
from model import EmbeddingModel
from sqlite_utils import get_indices_by_rowid

def fetch_sentence_data_from_document(cursor, rowid):
    """
    Retrieves sentence metadata (path, page, sub-index) from DB 
    and then reconstructs sentence text from the document.
    Returns a dictionary with all this info, or None if essential data is missing.
    The 'text' field in the dictionary can be None if reconstruction fails or is not applicable.
    """
    # Retrieve sentence details from SQLite based on rowid
    # The cursor is no longer needed for get_indices_by_rowid as it handles its own connections
    indices_data = get_indices_by_rowid(int(rowid))
    if not indices_data:
        print(f"No index data found in DB for rowid: {rowid}")
        return None

    file_path_from_db = indices_data.get('path') # path in DB might be relative to target_dir
    page_idx = indices_data.get('id') # 'id' column in DB stores page_index
    sub_idx = indices_data.get('sub_index')

    if file_path_from_db is None or page_idx is None or sub_idx is None:
        print(f"Incomplete index data for rowid: {rowid} - Path: {file_path_from_db}, Page: {page_idx}, Sub: {sub_idx}")
        return None
    
    # Resolve the full path to the document
    # Assuming paths in DB might be relative to Config.getTargetDirectory()
    # If file_path_from_db is already absolute, os.path.join behaves correctly.
    target_dir = Config.getTargetDirectory()
    full_doc_path = os.path.join(target_dir, file_path_from_db)
    if not os.path.exists(full_doc_path):
        # If not found with target_dir, try using file_path_from_db as is (maybe it was absolute)
        if os.path.exists(file_path_from_db):
            full_doc_path = file_path_from_db
        else:
            print(f"Document not found for rowid {rowid}. Tried path: {full_doc_path} (and {file_path_from_db})")
            return {
                'path': file_path_from_db, # Return original path from DB for context
                'page_index': page_idx,
                'sub_index': sub_idx,
                'text': None # Text cannot be retrieved
            }

    sentence_text = None
    file_extension = os.path.splitext(full_doc_path)[1].lower()

    if file_extension == '.pdf':
        sentence_text = get_sentence_by_indices(full_doc_path, page_idx, sub_idx)
        if not sentence_text:
            print(f"Could not reconstruct sentence from PDF: {full_doc_path}, Page: {page_idx}, Sub: {sub_idx}")
    else:
        print(f"Sentence text retrieval for non-PDF file type ('{file_extension}') not yet implemented via direct text reconstruction. Rowid: {rowid}")
        # For non-PDFs, sentence_text remains None. Caller must handle this.

    return {
        'path': file_path_from_db, # Return original path from DB that was used for lookup
        'page_index': page_idx,
        'sub_index': sub_idx,
        'text': sentence_text 
    }

def search_index(query, top_k=5, model_service=None):
    """
    Search the vector index for similar sentences to the query.
    Returns the top_k most similar sentences with their metadata.
    
    Args:
        query: Query string or embedding
        top_k: Number of results to return
        model_service: Optional ModelService instance. If None, uses global ModelService instance
    """
    print(f"Searching index for query: {query}")
    # Load the FAISS index
    vector_index_path = VECTOR_INDEX_FILE
    db_path = SQLITE_DB_FILE
    
    print(f"Looking for vector index at: {vector_index_path}")
    print(f"Looking for database at: {db_path}")
    print(f"INDEX_DIR exists: {os.path.exists(INDEX_DIR)}")
    print(f"Vector index exists: {os.path.exists(vector_index_path)}")
    print(f"Database exists: {os.path.exists(db_path)}")
    
    try:
        vector_index = faiss.read_index(vector_index_path)
    except Exception as e:
        raise RuntimeError(f"Failed to load vector index: {str(e)}")

    # Connect to SQLite database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
    except Exception as e:
        raise RuntimeError(f"Failed to connect to database: {str(e)}")

    # Get query embedding
    try:
        if model_service is not None:
            query_embedding = model_service.encode(query)
            print(f"Query embedding shape: {query_embedding.shape}")
            print(f"Query embedding dtype: {query_embedding.dtype}")
        else:
            # Use EmbeddingModel like summarize.py
            model = EmbeddingModel()  # Will reuse existing instance due to singleton pattern
            # Wait for model to be ready
            while not model.is_ready():
                time.sleep(0.1)
            query_embedding = model.encode(query)
       

    except Exception as e:
        raise RuntimeError(f"Failed to get query embedding: {str(e)}")
    
    # Search the index with a larger k to get more candidates
    search_k = top_k * 2  # Search for more results than we need
    try:
        # Ensure it's a 2D array and float32 for FAISS
        search_embedding = query_embedding.astype(np.float32)
        if search_embedding.ndim == 1:
            search_embedding = search_embedding.reshape(1, -1)
        
        distances, indices = vector_index.search(search_embedding, search_k)
        print(f"Search returned {len(indices[0])} results")

    except Exception as e:
        raise RuntimeError(f"Failed to search index: {str(e)}")
    
    # Collect results with deduplication
    results = []
    seen_sentences = set()  # Track seen sentences to avoid duplicates
    min_distance_diff = 0.01  # Minimum distance difference to consider results unique
    
    try:
        last_distance = None
        for idx, distance in zip(indices[0], distances[0]):
            retrieved_data = fetch_sentence_data_from_document(cursor, int(idx))
            
            # Skip if essential data or sentence text couldn't be retrieved
            if not retrieved_data or retrieved_data.get('text') is None:
                print(f"Skipping result for rowid {idx} due to missing data or text.")
                continue
                
            current_sentence_text = retrieved_data['text']
            # Skip if we've seen this exact sentence before
            if current_sentence_text in seen_sentences:
                print(f"Skipping duplicate sentence: {current_sentence_text[:50]}...")
                continue
                
            # Skip if the distance is too close to the last result
            if last_distance is not None and abs(distance - last_distance) < min_distance_diff:
                print(f"Skipping similar distance result: {distance} vs {last_distance}")
                continue
                
            seen_sentences.add(current_sentence_text)
            last_distance = distance
            
            results.append({
                'file': retrieved_data['path'],
                'sentence': current_sentence_text,
                'indices': retrieved_data['page_index'],
                'sub_index': retrieved_data['sub_index'],
                'distance': float(distance)
            })
            print(green(f"Added result: {current_sentence_text[:50]}..."))
            
            if len(results) >= top_k:
                break
                
    except Exception as e:
        print(f"Error processing results: {str(e)}")
        raise
    finally:
        conn.close()
    
    return results

def extract_page_from_file(filepath, indices):
    """
    Extract text from a specific page/section of a file based on its format.
    """
    if isinstance(indices, int):
        indices = [indices]
    
    file_extension = os.path.splitext(filepath)[1].lower()
    
    # Map file extensions to their extraction functions
    extractors = {
        '.pdf': lambda f: extract_text_from_pdf_page,
        # '.txt': extract_text_from_txt,
        # '.docx': extract_text_from_docx,
        # '.doc': extract_text_from_doc,
        # '.rtf': extract_text_from_rtf,
        # '.epub': extract_text_from_epub
    }
    
    try:
        if file_extension not in extractors:
            raise ValueError(f"Unsupported file format: {file_extension}")
            
        extractor = extractors[file_extension]
        
        # Special handling for PDF since it has a different return format
        if file_extension == '.pdf':
            extract_func = extractor(filepath)
            # For PDFs, we need to handle each page index separately
            all_text = []
            for page_idx in indices:
                try:
                    page_text = extract_func(filepath, page_idx)
                    all_text.extend(page_text)
                except Exception as e:
                    print(f"Error extracting page {page_idx}: {str(e)}")
            return ' '.join(all_text)
        
        # Handle all other formats that return (sentences, page_indices)
        sentences, page_indices = extractor(filepath)
        relevant_sentences = [s for i, s in enumerate(sentences) if page_indices[i] in indices]
        return ' '.join(relevant_sentences)
            
    except Exception as e:
        print(f"Error extracting text from {filepath}: {str(e)}")
        return ""

def print_context(file_path, indices, sentence):
    """
    Print the context from the file for the given indices and highlight the sentence.
    """
    page_text = extract_page_from_file(file_path, indices)
    if page_text:
        # Highlight the sentence in the context
        highlighted_text = page_text.replace(sentence, f"\033[93m{sentence}\033[0m")
        print(highlighted_text)
    else:
        print("Could not extract context from file.")
    print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Search indexed PDF files using a query.')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--top_k', type=int, default=5,
                        help='Number of results to return (default: 5)')
    
    args = parser.parse_args()
    try:
        results = search_index(args.query, args.top_k)

        print(f"\nTop {args.top_k} matches for query: '{args.query}'\n")

        for i, result in enumerate(results, 1):
            file, page_idx, sub_idx, distance, sentence = result['file'], result['indices'], result.get('sub_index', 'N/A'), result['distance'], result['sentence']
            print(f"{i}. File: {file}")
            print(f"   Page Index: {page_idx}")
            print(f"   Sub Index: {sub_idx}")
            print(f"   Distance: {distance:.4f}")
            print(f"   Text: {sentence}\n")

            # Construct full path for print_context, similar to fetch_sentence_data_from_document
            target_dir = Config.getTargetDirectory()
            full_file_path_for_context = os.path.join(target_dir, file) if not os.path.isabs(file) else file
            # print_context(full_file_path_for_context, page_idx, sentence)
            # print()
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1) 