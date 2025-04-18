import faiss
import numpy as np
import argparse
import requests
import sqlite3
from parsers.pdf_utils import extract_text_from_pdf_page
from PyPDF2 import PdfReader
import os
import sys
from constants import APP_SUPPORT_PATH, INDEX_DIR, VECTOR_INDEX_FILE, SQLITE_DB_FILE
from index import get_target_directory
from utils import get_embedding
from sqlite_utils import get_sentence_by_id

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
        else:
            # Use our utility function
            query_embedding = get_embedding(query)
    except Exception as e:
        raise RuntimeError(f"Failed to get query embedding: {str(e)}")
    
    # Search the index
    try:
        distances, indices = vector_index.search(query_embedding.astype(np.float32), top_k)
        print(f"Search returned {len(indices[0])} results")
    except Exception as e:
        raise RuntimeError(f"Failed to search index: {str(e)}")
    
    # Collect results
    results = []
    
    try:
        for idx, distance in zip(indices[0], distances[0]):
            sentence_data = get_sentence_by_id(cursor, int(idx))
            if sentence_data:
                results.append({
                    'file': sentence_data['path'],
                    'sentence': sentence_data['sentence'],
                    'indices': sentence_data['id'],
                    'distance': float(distance)
                })
    except Exception as e:
        print(f"Error processing results: {str(e)}")
        raise
    finally:
        conn.close()
    
    # Sort results by distance
    results.sort(key=lambda x: x['distance'])
    return results[:top_k]

def extract_page_from_file(filepath, indices):
    """
    Extract text from a specific page/section of a file based on its format.
    """
    if isinstance(indices, int):
        indices = [indices]
    
    file_extension = os.path.splitext(filepath)[1].lower()
    
    # Map file extensions to their extraction functions
    extractors = {
        '.pdf': lambda f: (PdfReader(f), extract_text_from_pdf_page),
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
            reader, extract_func = extractor(filepath)
            # For PDFs, we need to handle each page index separately
            all_text = []
            for page_idx in indices:
                try:
                    page_text = extract_func(reader, page_idx)
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
            file, indices, distance, sentence = result['file'], result['indices'], result['distance'], result['sentence']
            print(f"{i}. File: {file}")
            print(f"   Index: {indices}")
            print(f"   Distance: {distance:.4f}")
            print(f"   Text: {sentence}\n")

            file_path = os.path.join(get_target_directory(), file)
            print_context(file_path, indices, sentence)
            print()
    except Exception as e:
        print(f"Error: {str(e)}") 