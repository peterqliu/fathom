import tkinter as tk
from tkinter import ttk

class FathomView:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Fathom")
        self.root.geometry("600x400")
        
        # Create a frame for better organization
        self.frame = ttk.Frame(self.root, padding="20")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Add label above the text box
        self.label = ttk.Label(self.frame, text="Query:")
        self.label.pack(pady=10)
        
        # Add text box
        self.query_entry = ttk.Entry(self.frame, width=50)
        self.query_entry.pack(pady=10)
        
        # Add submit button
        self.submit_button = ttk.Button(
            self.frame, 
            text="Submit", 
            command=self.handle_submit
        )
        self.submit_button.pack(pady=10)
    
    def handle_submit(self):
        query = self.query_entry.get()
        print(f"Query submitted: {query}")
    
    def run(self):
        self.root.mainloop() 