import os
import time
import numpy as np
import faiss
import sqlite3
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from index import process_file_for_indexing
from constants import VECTOR_INDEX_FILE, SQLITE_DB_FILE, CONFIG_FILE
from sqlite_utils import init_sqlite_db

def update_file_path(old_path, new_path):
    """
    Update the file path in the database for all rows matching the old path.
    This is used when a file is renamed or moved.
    
    Args:
        old_path (str): The original file path
        new_path (str): The new file path
    """
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(SQLITE_DB_FILE)
        cursor = conn.cursor()
        
        # Update all rows with the old path to use the new path
        cursor.execute('''
            UPDATE sentences 
            SET path = ? 
            WHERE path = ?
        ''', (new_path, old_path))
        
        # Save changes
        conn.commit()
        conn.close()
        
        print(f"Successfully updated path from {old_path} to {new_path}")
        
    except Exception as e:
        print(f"Error updating file path: {str(e)}")
        if 'conn' in locals():
            conn.close()
        raise

class FileHandler(FileSystemEventHandler):
    def __init__(self):
        # Get file directory from config
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.directory = config.get('targetDirectory')
                if not self.directory:
                    raise ValueError("targetDirectory not found in config file")
                self.directory = os.path.expanduser(self.directory)  # Expand ~ to home directory
        except FileNotFoundError:
            raise ValueError(f"Config file not found at {CONFIG_FILE}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in config file at {CONFIG_FILE}")
            
        self.vector_index = None
        self.load_existing_index()
        
    def load_existing_index(self):
        try:
            if os.path.exists(VECTOR_INDEX_FILE):
                print("Loading existing FAISS index...")
                self.vector_index = faiss.read_index(VECTOR_INDEX_FILE)
            else:
                print("No existing index found. Will create new one when needed.")
                self.vector_index = None
        except Exception as e:
            print(f"Error loading existing index: {str(e)}")
            self.vector_index = None
    
    def on_created(self, event):
        if not event.is_directory:
            filepath = event.src_path
            if filepath.lower().endswith(('.pdf', '.epub', '.txt', '.doc', '.docx', '.rtf')):
                print(f"New file detected: {filepath}")
                self.process_file(filepath)
    
    def on_deleted(self, event):
        if not event.is_directory:
            filepath = event.src_path
            if filepath.lower().endswith(('.pdf', '.epub', '.txt', '.doc', '.docx', '.rtf')):
                print(f"File deleted: {filepath}")
                try:
                    remove_file_embeddings(filepath)
                except Exception as e:
                    print(f"Error removing embeddings for {filepath}: {str(e)}")
                print('--------------------------------')
    
    def on_moved(self, event):
        if not event.is_directory:
            print(f"File renamed/moved:")
            print(f"  from: {event.src_path}")
            print(f"  to: {event.dest_path}")
            
            # Update the path in the database
            try:
                update_file_path(event.src_path, event.dest_path)
            except Exception as e:
                print(f"Error updating file path: {str(e)}")
            print('--------------------------------')
    
    def process_file(self, filepath):
        try:
            # Process the file and update index
            self.vector_index, success = process_file_for_indexing(
                filepath, self.directory, self.vector_index
            )
            
            if success:
                # Save updated index
                print(f"Saving updated index after processing {filepath}")
                faiss.write_index(self.vector_index, VECTOR_INDEX_FILE)
        except Exception as e:
            print(f"Error processing file {filepath}: {str(e)}")

def remove_file_embeddings(filepath):
    """
    Remove embeddings for a specific file from the FAISS index and SQLite database.
    Instead of deleting rows, we set path and sentence to NULL to preserve row IDs.
    
    Args:
        filepath (str): Path to the file to remove
    """
    try:
        # Load the FAISS index
        vector_index = faiss.read_index(VECTOR_INDEX_FILE)
        
        # Connect to SQLite database
        conn = sqlite3.connect(SQLITE_DB_FILE)
        cursor = conn.cursor()
        
        # Find all rows with matching path and get their ids
        cursor.execute('SELECT id FROM sentences WHERE path = ?', (filepath,))
        rows = cursor.fetchall()
        
        if not rows:
            print(f"File {filepath} not found in database")
            return
            
        # Get the IDs to remove from vector index
        ids_to_remove = np.array([row[0] for row in rows], dtype=np.int64)
        
        # Remove vectors by their IDs
        vector_index.remove_ids(ids_to_remove)
        
        # Update rows to set path and sentence to NULL instead of deleting
        cursor.execute('''
            UPDATE sentences 
            SET path = NULL, sentence = NULL 
            WHERE path = ?
        ''', (filepath,))
        
        # Save changes
        conn.commit()
        conn.close()
        faiss.write_index(vector_index, VECTOR_INDEX_FILE)
        
        print(f"Successfully removed embeddings for {filepath}")
        
    except Exception as e:
        print(f"Error removing embeddings: {str(e)}")
        if 'conn' in locals():
            conn.close()
        raise

def watch_directory(directory):
    # Initialize SQLite database
    init_sqlite_db()
    
    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()
    
    try:
        print(f"Watching directory: {directory}")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopping directory watcher...")
    observer.join()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python watch.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    watch_directory(directory) 