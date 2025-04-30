import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import traceback
from query import search_index
import logging
import threading
import os
import json

# Set up logger
logger = logging.getLogger(__name__)

# Import index_directory function only when needed to avoid circular imports
def get_index_directory_function():
    from index import index_directory
    return index_directory

class SearchBar(ttk.Frame):
    def __init__(self, parent, submit_callback, model_service):
        """Initialize the search bar with directory selection and search functionality
        
        Args:
            parent: Parent widget
            submit_callback: Callback function(query: str, target_directory: str)
            model_service: ModelService instance for embeddings
        """
        super().__init__(parent, padding="20")
        self.submit_callback = submit_callback
        self.model_service = model_service
        self.config_file = self._get_config_path()
        self.target_directory = self._load_target_directory()
        self.setup_ui()
        
        # Update UI with loaded directory
        if self.target_directory:
            self._update_dir_label(self.target_directory)
        
    def _get_config_path(self):
        """Get the path to config.json"""
        if getattr(sys, 'frozen', False):
            # We are running in a bundle
            config_dir = os.path.expanduser('~/Library/Application Support/Fathom/constants')
        else:
            # We are running in a normal Python environment
            config_dir = "constants"
        
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'config.json')
    
    def _load_target_directory(self):
        """Load target directory from config"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('targetDirectory')
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
        return None
    
    def _save_target_directory(self, directory):
        """Save target directory to config"""
        try:
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            
            config['targetDirectory'] = directory
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {str(e)}")
            messagebox.showerror("Error", f"Failed to save directory setting: {str(e)}")

    def setup_ui(self):
        """Setup the search bar UI components"""
        # Directory selection frame
        dir_frame = ttk.Frame(self)
        dir_frame.pack(fill=tk.X, pady=10)
        
        # Create a top frame for buttons
        button_frame = ttk.Frame(dir_frame)
        button_frame.pack(fill=tk.X, padx=0)
        
        # Directory selection button and index button in top frame
        self.dir_button = ttk.Button(
            button_frame,
            text="Directory",
            command=self._show_dir_dialog
        )
        self.dir_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Index button next to directory button
        self.index_button = ttk.Button(
            button_frame,
            text="Reindex",
            command=self._handle_index
        )
        self.index_button.pack(side=tk.LEFT)
        
        # Directory label below buttons
        self.dir_label = ttk.Label(
            dir_frame,
            text="No directory selected",
            wraplength=400
        )
        self.dir_label.pack(fill=tk.X, expand=True, pady=(5, 0))
        
        # Search controls
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, pady=10)
        
        self.query_entry = ttk.Entry(search_frame, width=50, font=('TkDefaultFont', 12))
        self.query_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        # Bind Enter key to handle_submit method
        self.query_entry.bind('<Return>', self._handle_submit)

    def _show_dir_dialog(self):
        """Show directory selection dialog and update the UI"""
        try:
            # Get root window
            root = self.winfo_toplevel()
            
            # Show directory selection dialog
            initial_dir = self.target_directory if self.target_directory else os.path.expanduser("~")
            selected_dir = filedialog.askdirectory(
                title="Select Directory",
                initialdir=initial_dir,
                parent=root
            )
            
            if selected_dir:  # User didn't cancel
                self.target_directory = selected_dir
                self._update_dir_label(selected_dir)
                self._save_target_directory(selected_dir)
            
            # Give focus back to entry
            self.query_entry.focus_set()
            
        except Exception as e:
            logger.error(f"Error selecting directory: {str(e)}")
            messagebox.showerror("Error", f"Failed to select directory: {str(e)}")
            
    def _update_dir_label(self, path):
        """Update the directory label with truncated path if necessary"""
        try:
            display_path = path if len(path) <= 50 else "..." + path[-47:]
            self.dir_label.configure(text=display_path)
        except Exception as e:
            logger.error(f"Error updating directory label: {str(e)}")
            messagebox.showerror("Error", f"Failed to update directory label: {str(e)}")

    def select_directory(self):
        """Deprecated - kept for compatibility"""
        self._show_dir_dialog()

    def _handle_index(self):
        """Handle indexing the selected directory"""
        if not self.target_directory:
            messagebox.showerror("Error", "Please select a directory first")
            return
            
        try:
            logger.debug(f"Starting indexing process for directory: {self.target_directory}")
            
            # Get the index_directory function
            index_directory = get_index_directory_function()
            logger.debug("Successfully imported index_directory function")
            
            # Get the appropriate index directory path
            if getattr(sys, 'frozen', False):
                app_support = os.path.expanduser('~/Library/Application Support/Fathom')
                index_dir = os.path.join(app_support, 'index')
            else:
                # Use absolute path even in development
                index_dir = os.path.abspath('index')
            
            os.makedirs(index_dir, exist_ok=True)
            logger.debug(f"Using index directory: {index_dir}")
            
            # Start indexing in a separate thread to keep UI responsive
            def index_thread():
                try:
                    logger.debug("Index thread started")
                    self.index_button.configure(state='disabled', text='Indexing...')
                    
                    # Wait for model service to be ready
                    if not self.model_service.is_ready():
                        logger.debug("Waiting for model service to be ready...")
                        if not self.model_service.wait_until_ready(timeout=60):
                            raise RuntimeError("Model service failed to initialize")
                    logger.debug("Model service is ready")
                    
                    # Use the shared wrapper class
                    from utils.model_wrapper import ModelServiceWrapper
                    wrapped_model_service = ModelServiceWrapper(self.model_service)
                    
                    logger.debug("Starting directory indexing...")
                    index_directory(self.target_directory, model_service=wrapped_model_service)
                    logger.debug("Directory indexing completed")
                    
                    self.index_button.configure(state='normal', text='Index')
                    
                except Exception as e:
                    logger.error(f"Indexing failed: {str(e)}")
                    logger.error(traceback.format_exc())
                    self.index_button.configure(state='normal', text='Index')
                    messagebox.showerror("Error", f"Failed to index directory: {str(e)}")
            
            thread = threading.Thread(target=index_thread)
            thread.daemon = True
            thread.start()
            logger.debug("Started indexing thread")
            
        except Exception as e:
            logger.error(f"Error starting indexing: {str(e)}")
            logger.error(traceback.format_exc())
            messagebox.showerror("Error", f"Failed to start indexing: {str(e)}")

    def _handle_submit(self, event=None):
        """Handle search submission from Enter key"""
        query = self.query_entry.get()
        if query.strip():  # Only submit if query is not empty
            logger.debug(f"Submit triggered for query: {query} with target directory: {self.target_directory}")
            self.submit_callback(query, target_directory=self.target_directory)

class ResultsDisplay(ttk.Frame):
    def __init__(self, parent):
        """Initialize the results display area
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent, padding="20")
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the results display UI components"""
        # Results text area with scrolling
        self.result_text = tk.Text(self, height=30, width=60, font=('TkDefaultFont', 12))
        self.result_text.pack(pady=10)
        
        # Configure text styles
        self.result_text.tag_configure('heading', font=('TkDefaultFont', 14, 'bold'))
        self.result_text.tag_configure('content', font=('TkDefaultFont', 12))
    
    def clear(self):
        """Clear all text from the display"""
        logger.debug("Clearing results display")
        self.result_text.delete('1.0', tk.END)
    
    def show_processing(self):
        """Show processing message"""
        logger.debug("Showing processing message")
        self.clear()
        self.result_text.insert('1.0', "Processing...\n", 'heading')
        # Force update to show processing message
        self.update_idletasks()
    
    def show_results(self, query, results):
        """Display search results
        
        Args:
            query: Search query string
            results: List of result dictionaries with 'file', 'distance', and 'sentence' keys
        """
        logger.debug(f"Displaying results for query: {query}")
        self.clear()
        self.result_text.insert(tk.END, f"Results for: {query}\n\n", 'heading')
        
        for i, result in enumerate(results, 1):
            logger.debug(f"Adding result {i}: {result['file']}")
            self.result_text.insert(tk.END, f"\nMatch {i}:\n", 'heading')
            self.result_text.insert(tk.END, f"File: {result['file']}\n", 'content')
            self.result_text.insert(tk.END, f"Score: {result['distance']:.4f}\n", 'content')
            self.result_text.insert(tk.END, f"Text: {result['sentence']}\n", 'content')
        
        # Force update to show results immediately
        self.update_idletasks()
    
    def show_error(self, error_msg):
        """Display error message
        
        Args:
            error_msg: Error message to display
        """
        logger.debug(f"Showing error: {error_msg}")
        self.clear()
        self.result_text.insert('1.0', f"Error: {error_msg}", 'heading')
        # Force update to show error immediately
        self.update_idletasks()

class FathomView:
    def __init__(self, model_service):
        self.window = tk.Tk()
        self.window.overrideredirect(True)  # Removes window decorations
        self.model_service = model_service
        
        # Variables to track mouse position for dragging
        self._drag_data = {"x": 0, "y": 0}
        
        # Add escape key to quit
        self.window.bind('<Escape>', lambda e: self.window.quit())
        
        self.setup_loading_screen()
        
    def _on_drag_start(self, event):
        """Begin drag of window"""
        # Only start drag if the event originated from a Frame or Label
        # (i.e. background elements), not from buttons or entry fields
        widget = event.widget
        if isinstance(widget, (tk.Frame, ttk.Frame, tk.Label, ttk.Label)):
            self._drag_data["x"] = event.x
            self._drag_data["y"] = event.y
            
    def _on_drag_motion(self, event):
        """Handle window dragging"""
        # Only drag if we have valid start coordinates and event is from background
        widget = event.widget
        if isinstance(widget, (tk.Frame, ttk.Frame, tk.Label, ttk.Label)) and \
           self._drag_data["x"] != 0:  # Check if drag was started
            # Calculate new position
            deltax = event.x - self._drag_data["x"]
            deltay = event.y - self._drag_data["y"]
            x = self.window.winfo_x() + deltax
            y = self.window.winfo_y() + deltay
            
            # Move window
            self.window.geometry(f"+{x}+{y}")
            
    def _bind_draggable(self, widget):
        """Make a widget draggable for window movement"""
        widget.bind('<Button-1>', self._on_drag_start)
        widget.bind('<B1-Motion>', self._on_drag_motion)
        widget.bind('<ButtonRelease-1>', lambda e: self._drag_data.update({"x": 0, "y": 0}))
        
    def setup_loading_screen(self):
        # Create loading screen elements
        self.loading_frame = tk.Frame(self.window, bg='white')
        self.loading_label = tk.Label(
            self.loading_frame, 
            text="Initializing model...\nPlease wait.",
            bg='white', 
            font=('Arial', 12)
        )
        self.loading_label.pack(expand=True)
        self.loading_frame.pack(fill='both', expand=True)
        
        # Make loading screen draggable
        self._bind_draggable(self.loading_frame)
        self._bind_draggable(self.loading_label)
        
        # Center the window - do this after packing all elements
        width, height = 300, 100
        
        # First update the window to ensure proper size calculation
        self.window.update_idletasks()
        
        # Get screen dimensions
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Calculate center position
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Set window size and position
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Force another update to ensure centering takes effect
        self.window.update_idletasks()
    
    def show_main_content(self):
        # Remove loading screen
        self.loading_frame.destroy()
        
        # Setup your main UI components here
        self.setup_main_ui()
        
        # Configure the theme
        style = ttk.Style()
        style.configure('TFrame', background='#1a2a3a')
        style.configure('TLabel', background='#1a2a3a', foreground='white')
        style.configure('TEntry', padding=5)
        style.configure('TButton', padding=5)
        
        # Set window attributes
        self.window.title("Fathom")
        self.window.attributes('-alpha', 0.9)
        self.window.overrideredirect(True)
        
        # Center the window - do this last after all UI components are set up
        width, height = 800, 600
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Update window geometry once with both size and position
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Force window to update and redraw
        self.window.update_idletasks()
    
    def check_model_ready(self):
        if self.model_service.wait_until_ready(timeout=60):
            self.show_main_content()
        else:
            self.loading_label.config(
                text="Error: Model failed to initialize\nPlease restart the application"
            )
            self.window.after(3000, self.window.quit)
    
    def setup_main_ui(self):
        # Create main components
        self.search_bar = SearchBar(self.window, self.handle_submit, self.model_service)
        self.search_bar.pack(fill=tk.X)
        
        self.results_display = ResultsDisplay(self.window)
        self.results_display.pack(fill=tk.BOTH, expand=True)
        
        # Make frames draggable
        self._bind_draggable(self.search_bar)
        self._bind_draggable(self.results_display)
    
    def handle_submit(self, query, target_directory=None):
        """Handle search submission
        
        Args:
            query: Search query string
            target_directory: Target directory to search in (used for logging only)
        """
        if not query.strip():
            return
            
        try:
            logger.debug(f"Processing search query: {query} in directory: {target_directory}")
            self.results_display.show_processing()
            
            # Use the shared wrapper class
            from utils.model_wrapper import ModelServiceWrapper
            wrapped_model_service = ModelServiceWrapper(self.model_service)
            
            logger.debug("Searching index...")
            results = search_index(query, top_k=5, model_service=wrapped_model_service)
            logger.debug(f"Search complete, found {len(results) if results else 0} results")
            logger.debug(f"Results before display: {results}")
            
            if results:
                self.results_display.show_results(query, results)
            else:
                logger.debug("No results found")
                self.results_display.show_error("No results found")
            
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            logger.error(traceback.format_exc())
            self.results_display.show_error(str(e))
    
    def run(self):
        # Start checking model status in background
        thread = threading.Thread(target=self.check_model_ready)
        thread.daemon = True
        thread.start()
        
        # Start the main event loop
        self.window.mainloop() 