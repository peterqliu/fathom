import os
import json
import numpy as np
import faiss
from constants import VECTOR_INDEX_FILE, CLUSTERS_FILE
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
    Remove embeddings for a specific file from the FAISS index and metadata.
    
    Args:
        filename (str): Name of the file to remove (will be matched against relative paths)
    """
    try:
        # Load existing metadata
        with open(CLUSTERS_FILE, 'r', encoding='utf-8') as f:
            all_clusters = json.load(f)
        
        # Find the file and its ID range in metadata
        file_index = None
        for i, file_info in enumerate(all_clusters['files']):
            full_path = os.path.join(get_target_directory(), file_info['path'])
            if filename in full_path:
                file_index = i
                break
        
        if file_index is None:
            print(f"File {filename} not found in metadata")
            return
        
        # Get the ID range to remove
        file_info = all_clusters['files'][file_index]
        ids_to_remove = np.arange(file_info['id_start'], file_info['id_end'], dtype=np.int64)
        # Load the FAISS index
        vector_index = faiss.read_index(VECTOR_INDEX_FILE)
        # Remove vectors by their IDs
        vector_index.remove_ids(ids_to_remove)
        # Update metadata
        all_clusters['files'].pop(file_index)
        # Save updated index and metadata
        faiss.write_index(vector_index, VECTOR_INDEX_FILE)
        with open(CLUSTERS_FILE, 'w') as f:
            json.dump(all_clusters, f, indent=4, ensure_ascii=False)
        
        print(f"Successfully removed embeddings for {filename}")
        
    except Exception as e:
        print(f"Error removing embeddings: {str(e)}")

if __name__ == "__main__":
    # Get the target directory to watch
    directory = get_target_directory()
    print(f"Watching directory: {directory}")
    start_watching(directory) 