import customtkinter as ctk
import watch as watch  # Import the watch module from server directory
import constants  # Import constants module
import json  # Import json for reading and writing config

from vectorIndex_utils import VectorIndex # Import VectorIndex
import multiprocessing # Import multiprocessing
from view import View # Import the View class

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Ensure all required directories exist
        constants.ensure_directories()
        
        # Create and store the main VectorIndex instance
        self.vector_index_instance = VectorIndex()
        
        # Initialize the View
        self.view = View(self) # Pass self (App instance) as the controller/master
        
        # Setup the UI via the View class
        self.view.setup_ui()
        
        # Start file watcher with the VectorIndex instance and callback to View's method
        self.file_observer = watch.start_watching(
            self.vector_index_instance, 
            callback=self.view.update_ui_from_watch # Use view's method for UI updates
        )
        
        # Initialize the embedding model (Commented out as it's not used)
        # self.model = EmbeddingModel()

    # Controller logic has been moved to the View class
        
    def on_closing(self):
        # Stop the file watcher when the app is closed
        if hasattr(self, 'file_observer'):
            self.file_observer.stop()
            self.file_observer.join()
        self.destroy()

if __name__ == "__main__":
    multiprocessing.freeze_support()  # Add this line
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)  # Set up clean shutdown
    app.mainloop() 