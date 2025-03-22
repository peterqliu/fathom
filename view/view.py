import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import traceback
from query import search_index
import logging
import threading
import os
import json

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SearchBar(ttk.Frame):
    def __init__(self, parent, submit_callback):
        """Initialize the search bar with directory selection and search functionality
        
        Args:
            parent: Parent widget
            submit_callback: Callback function(query: str, target_directory: str)
        """
        super().__init__(parent, padding="20")
        self.submit_callback = submit_callback
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
        
        # Directory selection button and label
        self.dir_button = ttk.Button(
            dir_frame,
            text="Select Directory",
            command=self._show_dir_dialog
        )
        self.dir_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.dir_label = ttk.Label(
            dir_frame,
            text="No directory selected",
            wraplength=400
        )
        self.dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Search controls
        self.query_entry = ttk.Entry(self, width=50, font=('TkDefaultFont', 12))
        self.query_entry.pack(pady=10)
        self.query_entry.bind('<Return>', self.handle_submit)
        
        self.submit_button = ttk.Button(
            self,
            text="Submit",
            command=self.handle_submit
        )
        self.submit_button.pack(pady=10)

    def handle_submit(self, event=None):
        """Handle search submission from either button click or Enter key"""
        query = self.query_entry.get()
        self.submit_callback(query, target_directory=self.target_directory)

    def _show_dir_dialog(self):
        """Show directory selection dialog and update the UI"""
        try:
            # Get root window and ensure it's visible
            root = self.winfo_toplevel()
            root.deiconify()
            root.lift()
            root.focus_force()
            
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
                
        except Exception as e:
            logger.error(f"Error selecting directory: {str(e)}")
            messagebox.showerror("Error", f"Failed to select directory: {str(e)}")
            
        finally:
            # Ensure window stays on top
            root.lift()
            root.focus_force()
    
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
        self.result_text.delete('1.0', tk.END)
    
    def show_processing(self):
        """Show processing message"""
        self.clear()
        self.result_text.insert('1.0', "Processing...\n", 'heading')
    
    def show_results(self, query, results):
        """Display search results
        
        Args:
            query: Search query string
            results: List of result dictionaries with 'file', 'distance', and 'sentence' keys
        """
        self.clear()
        self.result_text.insert(tk.END, f"Results for: {query}\n\n", 'heading')
        
        for i, result in enumerate(results, 1):
            self.result_text.insert(tk.END, f"\nMatch {i}:\n", 'heading')
            self.result_text.insert(tk.END, f"File: {result['file']}\n", 'content')
            self.result_text.insert(tk.END, f"Score: {result['distance']:.4f}\n", 'content')
            self.result_text.insert(tk.END, f"Text: {result['sentence']}\n", 'content')
    
    def show_error(self, error_msg):
        """Display error message
        
        Args:
            error_msg: Error message to display
        """
        self.clear()
        self.result_text.insert('1.0', f"Error: {error_msg}", 'heading')

class FathomView:
    def __init__(self, model_service):
        self.window = tk.Tk()
        self.window.overrideredirect(True)  # Removes window decorations
        self.model_service = model_service
        
        # Variables to track mouse position for dragging
        self._drag_data = {"x": 0, "y": 0}
        
        # Make entire window draggable
        self.window.bind('<Button-1>', self._on_drag_start)
        self.window.bind('<B1-Motion>', self._on_drag_motion)
        
        self.setup_loading_screen()
        
    def _on_drag_start(self, event):
        """Begin drag of window"""
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
    
    def _on_drag_motion(self, event):
        """Handle window dragging"""
        # Calculate new position
        deltax = event.x - self._drag_data["x"]
        deltay = event.y - self._drag_data["y"]
        x = self.window.winfo_x() + deltax
        y = self.window.winfo_y() + deltay
        
        # Move window
        self.window.geometry(f"+{x}+{y}")
    
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
        self.window.attributes('-topmost', True)
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
        self.search_bar = SearchBar(self.window, self.handle_submit)
        self.search_bar.pack(fill=tk.X)
        
        self.results_display = ResultsDisplay(self.window)
        self.results_display.pack(fill=tk.BOTH, expand=True)
    
    def handle_submit(self, query):
        if not query.strip():
            return
            
        try:
            self.results_display.show_processing()
            
            # Create wrapper for properly shaped embeddings
            class ModelServiceWrapper:
                def __init__(self, model_service):
                    self.model_service = model_service
                def encode(self, text):
                    embedding = self.model_service.encode(text)
                    return embedding.reshape(1, -1)
            
            wrapped_model_service = ModelServiceWrapper(self.model_service)
            results = search_index(query, top_k=5, model_service=wrapped_model_service)
            
            self.results_display.show_results(query, results)
            
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