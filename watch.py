import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from constants import Config, DEBUG_SKIP_INDEXING, DEBUG_SKIP_DELETING
from sqlite_utils import remove_sentences, remove_filename, rename_file
from vectorIndex_utils import VectorIndex
from index import process_file_for_indexing
from file_utils import red, green
import numpy as np


# Configure logging (for debugging only)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, vector_idx_instance: VectorIndex, callback: callable = None):
        self.callback = callback
        if vector_idx_instance is None:
            raise ValueError("A VectorIndex instance must be provided to FileChangeHandler.")
        self.vector_idx = vector_idx_instance
        super().__init__()
    
    def _should_ignore_event(self, event) -> bool:
        """Checks if the file event should be ignored based on defined rules."""
        if event.is_directory:
            return False # Don't ignore directory events with this rule

        # Rule: Ignore hidden files (starting with '.')
        if os.path.basename(event.src_path).startswith('.'):
            return True
        
        # For move events, also check the destination path
        if hasattr(event, 'dest_path') and event.dest_path and os.path.basename(event.dest_path).startswith('.'):
            return True
            
        return False
    
    def on_created(self, event):
        if self._should_ignore_event(event):
            return

        message = f"File created: {event.src_path}"
        self._notify(message)
        if DEBUG_SKIP_INDEXING:
            print(f"DEBUG: Skipping indexing for new file {event.src_path} due to DEBUG_SKIP_INDEXING flag.")
            return
        # Process the new file for indexing
        success = process_file_for_indexing(event.src_path, self.vector_idx)
        if success:
            print(green(f"Successfully indexed new file: {event.src_path}"))
        else:
            print(red(f"Failed to index new file: {event.src_path}"))
    
    def on_deleted(self, event):
        if self._should_ignore_event(event):
            return

        file_path = event.src_path
        message = f"File deleted: {file_path}"
        self._notify(message)

        if DEBUG_SKIP_DELETING:
            print(f"DEBUG: Skipping removal of indices for deleted file {file_path} due to DEBUG_SKIP_DELETING flag.")
            return
        
        deleted_rowids = remove_sentences(file_path)
        
        if deleted_rowids.size > 0:
            # Reload the index from disk to ensure it's fresh before attempting deletion
            self.vector_idx.index = self.vector_idx._load_or_initialize_index()
            if self.vector_idx.index is None:
                # Consider how to handle this case more gracefully
                remove_filename(file_path) # Ensure filename is removed from Filenames table regardless
                return

            print(f"Attempting to remove {len(deleted_rowids)} IDs from FAISS index for deleted file: {file_path}")
            removed_count = self.vector_idx.delete_with_ids(deleted_rowids)
            if removed_count > 0:
                print(green(f"Successfully removed {removed_count} vectors from FAISS index."))
                self.vector_idx.save_index()
            else:
                print(red(f"No vectors found in FAISS index for the given IDs, or delete operation failed."))
        else:
            print(f"No sentence IDs returned from SQLite for {file_path}, skipping FAISS index deletion.")

        remove_filename(file_path)
    
    def on_modified(self, event):
        # Log event type and is_directory status for debugging
        logging.info(f"on_modified event: type={type(event).__name__}, src_path='{event.src_path}', is_directory={event.is_directory}")

        if self._should_ignore_event(event):
            # logging.info(f"on_modified: Event for '{event.src_path}' ignored by _should_ignore_event.")
            return
        
        if event.is_directory:
            # logging.info(f"on_modified: Event for '{event.src_path}' is a directory modification, ignoring.")
            return # Ignore directory modifications for this handler

        # If we reach here, it should be a file modification event
        message = f"File modified: {event.src_path}"
        self._notify(message)
        print(f"File {event.src_path} modified. Consider re-indexing to update vector store.")
        # For more detailed debugging, let's also log the os.path.isfile status
        is_file = os.path.isfile(event.src_path)
        logging.info(f"on_modified: Verified event.src_path '{event.src_path}' with os.path.isfile: {is_file}")
    
    def on_moved(self, event):
        # Log event type and paths for debugging
        dest_path_info = event.dest_path if hasattr(event, 'dest_path') else 'N/A'
        logging.info(f"on_moved event: type={type(event).__name__}, src_path='{event.src_path}', dest_path='{dest_path_info}', is_directory={event.is_directory}")

        if self._should_ignore_event(event):
            # logging.info(f"on_moved: Event from '{event.src_path}' to '{dest_path_info}' ignored by _should_ignore_event.")
            return
        
        if not event.is_directory:
            # 1. Update database entries to reflect the new name
            rename_file(event.src_path, event.dest_path)
            logging.info(f"SQLite records updated for rename from '{event.src_path}' to '{event.dest_path}'. Index entries retained with new path.")
            
        else:
            logging.info(f"on_moved: Directory event from '{event.src_path}' to '{dest_path_info}' passed checks. No specific action taken for directory rename.")

        pass

    def _notify(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_message = f"{timestamp} - {message}"
        
        if self.callback:
            self.callback(formatted_message)
        else:
            logging.info(formatted_message)

def start_watching(vector_idx_instance: VectorIndex, directory_to_watch: str = None, callback: callable = None):
    if vector_idx_instance is None:
        print("Error: A VectorIndex instance must be provided to start_watching. File watcher cannot start.")
        return None

    actual_directory_to_watch = directory_to_watch
    if actual_directory_to_watch is None:
        print("Directory not provided, fetching watch directory from Config.")
        actual_directory_to_watch = Config.getTargetDirectory()
        if not actual_directory_to_watch:
            print("Error: Watch directory not found in Config and not provided. File watcher cannot start.")
            return None # Indicate failure
    
    print(f"FileChangeHandler will use the provided VectorIndex instance. Index file: {vector_idx_instance.index_file_path}")
    event_handler = FileChangeHandler(vector_idx_instance=vector_idx_instance, callback=callback)
    observer = Observer()
    observer.schedule(event_handler, actual_directory_to_watch, recursive=True)
    observer.start()
    print(f"Watching directory: {actual_directory_to_watch}")
    return observer 

if __name__ == "__main__":
    print("Starting file watcher from __main__ block in watch.py...")
    # Create the single VectorIndex instance
    # This instance would typically be created and managed by your main application logic.
    main_app_vector_index = VectorIndex()
    print(f"Main VectorIndex instance created. Index file: {main_app_vector_index.index_file_path}")

    watch_dir_for_main = Config.getTargetDirectory() 
    if watch_dir_for_main:
        def print_message_main(msg):
            print(f"MainCallback: {msg}")
        
        print(f"Calling start_watching with directory '{watch_dir_for_main}' and shared VectorIndex.")
        observer_instance = start_watching(
            vector_idx_instance=main_app_vector_index,
            directory_to_watch=watch_dir_for_main, 
            callback=print_message_main
        )
        if observer_instance:
            print("Observer started successfully from __main__.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("KeyboardInterrupt received, stopping observer...")
                observer_instance.stop()
                print("Observer stopped by main.")
            observer_instance.join()
            print("Observer joined.")
    else:
        print("Watch directory not configured in constants. Exiting main test block in watch.py.") 