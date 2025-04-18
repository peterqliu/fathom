import os
import json
import numpy as np
import faiss
import sqlite3
from constants import VECTOR_INDEX_FILE, CLUSTERS_FILE, SQLITE_DB_FILE
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from index import get_target_directory

# File system event handler
class FileChangeHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"File created: {event.src_path}")
            print('--------------------------------')

    def on_deleted(self, event):
        if not event.is_directory:
            print(f"File deleted: {event.src_path}")
            try:
                remove_file_embeddings(event.src_path)
            except Exception as e:
                print(f"Error removing embeddings for {event.src_path}: {str(e)}")
            print('--------------------------------')
            
    def on_moved(self, event):
        print('event', event)
        if not event.is_directory:
            print(f"File renamed/moved:")
            print(f"  from: {event.src_path}")
            print(f"  to: {event.dest_path}")
            print('--------------------------------')

def start_watching(directory):
    """
    Start watching the specified directory for file changes.
    
    Args:
        directory (str): Path to the directory to watch
    """
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def remove_file_embeddings(filename):
    """
    Remove embeddings for a specific file from the FAISS index and SQLite database.
    
    Args:
        filename (str): Name of the file to remove (will be matched against relative paths)
    """
    try:
        # Load the FAISS index
        vector_index = faiss.read_index(VECTOR_INDEX_FILE)
        
        # Connect to SQLite database
        conn = sqlite3.connect(SQLITE_DB_FILE)
        cursor = conn.cursor()
        
        # Find all rows with matching path and get their ids
        cursor.execute('SELECT id FROM sentences WHERE path LIKE ?', (f'%{filename}%',))
        rows = cursor.fetchall()
        
        if not rows:
            print(f"File {filename} not found in database")
            return
            
        # Get the IDs to remove from vector index
        ids_to_remove = np.array([row[0] for row in rows], dtype=np.int64)
        
        # Remove vectors by their IDs
        vector_index.remove_ids(ids_to_remove)
        
        # Update metadata in SQLite - set path and sentence to NULL for matching rows
        cursor.execute('UPDATE sentences SET path = NULL, sentence = NULL WHERE path LIKE ?', (f'%{filename}%',))
        
        # Save changes
        conn.commit()
        conn.close()
        faiss.write_index(vector_index, VECTOR_INDEX_FILE)
        
        print(f"Successfully removed embeddings for {filename}")
        
    except Exception as e:
        print(f"Error removing embeddings: {str(e)}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Get the target directory to watch
    directory = get_target_directory()
    print(f"Watching directory: {directory}")
    start_watching(directory) 