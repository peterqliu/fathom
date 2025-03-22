import tkinter as tk
import threading
import logging

logger = logging.getLogger(__name__)

class LoadingScreen:
    def __init__(self, width=300, height=100):
        self.window = tk.Tk()
        self.window.title("Loading")
        self.window.geometry(f"{width}x{height}")
        self.window.configure(bg='white')
        
        # Center the window
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
        self.label = tk.Label(self.window, text="Initializing model...\nPlease wait.", 
                            bg='white', font=('Arial', 12))
        self.label.pack(expand=True)
    
    def show_error(self, message="Error occurred", close_delay=3000):
        """Show error message and close after delay"""
        self.label.config(text=message)
        self.window.after(close_delay, self.window.destroy)
    
    def close(self):
        """Close the loading screen"""
        self.window.destroy()
    
    def start_loading(self, initialization_func, success_callback):
        """
        Start loading process with given initialization function
        
        Args:
            initialization_func: Function that returns True if initialization successful
            success_callback: Function to call after successful initialization
        """
        def check_ready():
            try:
                if initialization_func():
                    self.close()
                    success_callback()
                else:
                    self.show_error("Error: Model failed to initialize\nPlease restart the application")
            except Exception as e:
                logger.exception("Error during initialization")
                self.show_error(f"Error: {str(e)}\nPlease restart the application")
        
        thread = threading.Thread(target=check_ready)
        thread.daemon = True
        thread.start()
        
        self.window.mainloop() 