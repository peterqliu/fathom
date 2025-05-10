import customtkinter as ctk
from customtkinter import CTkFrame, CTkLabel, CTkButton, CTkTextbox, CTkEntry # CTkScrollableFrame no longer needed directly by View
import tkinter # Added tkinter
from tkinter import messagebox # filedialog is now in view_handlers, messagebox stays for View's helpers
# import os # Moved to view_handlers
# import constants # Only if PADDING_X/Y were from there, otherwise not needed directly by View
# from query import search_index, extract_page_from_file # Moved to view_handlers
# from index import index_directory # Moved to view_handlers
from view_handlers import ViewHandlers # Import the new handlers class

# New CustomScrollableFrame class (re-instated)
class CustomScrollableFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Use the master's theme for canvas background initially
        canvas_bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        self.canvas = tkinter.Canvas(self, borderwidth=0, highlightthickness=0, background=canvas_bg)
        self.scrollbar = ctk.CTkScrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.interior_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.interior_frame.grid_columnconfigure(0, weight=1)

        self.interior_window = self.canvas.create_window((0, 0), window=self.interior_frame, anchor="nw")

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.interior_frame.bind("<Configure>", self._on_interior_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel scrolling - binding to canvas should be sufficient if focus is managed
        self.canvas.bind("<MouseWheel>", self._on_mousewheel) # Windows & macOS
        self.canvas.bind("<Button-4>", self._on_mousewheel)   # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mousewheel)   # Linux scroll down

    def _on_interior_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        self.canvas.itemconfig(self.interior_window, width=self.canvas.winfo_width())

    def _on_mousewheel(self, event):
        # If this method is called, the event was bound to self.canvas.
        # We determine direction and scroll. The focus should ideally be on the canvas.
        if event.num == 4 or event.delta > 0:  # Scroll up (Linux button 4 or positive delta for Windows/macOS)
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:  # Scroll down (Linux button 5 or negative delta for Windows/macOS)
            self.canvas.yview_scroll(1, "units")

    def get_content_frame(self):
        return self.interior_frame

    def update_scrollregion(self):
        self.interior_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        if hasattr(self, 'canvas'): # Ensure canvas exists
            canvas_bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
            self.canvas.configure(background=canvas_bg)
            self.interior_frame.configure(fg_color="transparent") # Keep interior transparent relative to canvas


class View:
    def __init__(self, app_controller):
        self.app_controller = app_controller
        self.master = app_controller # The main App instance is the master for UI components
        self.handlers = ViewHandlers(self) # Instantiate ViewHandlers

        # Constants (can be defined locally if not from constants module)
        self.PADDING_X = 20
        self.PADDING_Y = 10
        self.DEFAULT_MIN_WRAPLENGTH = 50
        self.INITIAL_FALLBACK_WRAPLENGTH = 230

    def setup_ui(self):
        """Set up all UI components declaratively"""
        # Configure window (master is the App instance, which is a ctk.CTk)
        self.master.title("Minimal CustomTkinter App")
        self.master.geometry("400x750")

        # Configure grid layout on master
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_rowconfigure(0, weight=1)

        # Create main frame
        self.frame = ctk.CTkFrame(self.master)
        self.frame.grid(row=0, column=0, padx=self.PADDING_X, pady=self.PADDING_Y*2, sticky="nsew")
        # Configure a two-column layout for the frame
        self.frame.grid_columnconfigure((0, 1), weight=1) # Changed to configure two columns
        self.frame.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)

        # Define UI widgets declaratively
        widgets = [
            {
                "type": CTkLabel,
                "props": {
                    "text": "Waiting for file system events...",
                    "font": ("Helvetica", 16),
                    "wraplength": 350,
                    "justify": "left"
                },
                "attr_name": "label"
            },
            {
                "type": CTkEntry,
                "props": {
                    "placeholder_text": "query",
                    "font": ("Helvetica", 32)
                },
                "attr_name": "query_input"
            },
            {
                "type": "button_row",
                "buttons": [
                    {
                        "type": CTkButton,
                        "props": {
                            "text": "Clear Log",
                            "command": self.handlers.clear_log_ui
                        },
                        "attr_name": "button"
                    },
                    {
                        "type": CTkButton,
                        "props": {
                            "text": "Set directory",
                            "command": self.handlers.select_directory_ui
                        },
                        "attr_name": "dir_button"
                    },
                    {
                        "type": CTkButton,
                        "props": {
                            "text": "Index",
                            "command": self.handlers.on_index_click_ui
                        },
                        "attr_name": "index_button"
                    }
                ],
                "attr_name": "button_frame"
            },
            {
                "type": CTkTextbox,
                "props": {
                    "height": 100
                },
                "attr_name": "event_log"
            }
        ]

        # Create widgets from declarative definition
        self.create_widgets_from_definition(widgets)

        # Bind Enter key to query input
        self.query_input.bind("<Return>", self.handlers.on_query_submit_ui) # Use handler method

    def create_widgets_from_definition(self, widget_defs):
        """Create widgets from a declarative definition"""
        current_row = 0 # Keep track of the current row in the main frame
        for widget_def in widget_defs:
            if widget_def["type"] == "button_row":
                # Create a frame for the button row
                button_frame = CTkFrame(self.frame)
                button_frame.grid(row=current_row, column=0, padx=0, pady=self.PADDING_Y, sticky="ew")
                button_frame.grid_columnconfigure((0, 1, 2), weight=1) # 3 columns, equal weight
                setattr(self, widget_def["attr_name"], button_frame)

                for col_idx, button_def in enumerate(widget_def["buttons"]):
                    button = button_def["type"](button_frame, **button_def["props"])
                    button.grid(row=0, column=col_idx, padx=(0 if col_idx == 0 else self.PADDING_X/4, 0 if col_idx == 2 else self.PADDING_X/4), pady=0, sticky="ew")
                    setattr(self, button_def["attr_name"], button)
            elif widget_def["attr_name"] == "event_log":
                 widget = widget_def["type"](self.frame, **widget_def["props"])
                 widget.grid(row=current_row, column=0, padx=self.PADDING_X, pady=self.PADDING_Y, sticky="nsew")
                 setattr(self, widget_def["attr_name"], widget)
                 # Make event_log expand
                 self.frame.grid_rowconfigure(current_row, weight=10) # Give more weight to this row

            elif widget_def["attr_name"] == "query_input":
                widget = widget_def["type"](self.frame, **widget_def["props"])
                widget.grid(row=current_row, column=0, padx=self.PADDING_X, pady=self.PADDING_Y, sticky="ew")
                setattr(self, widget_def["attr_name"], widget)
            elif widget_def["attr_name"] == "results_frame":
                widget = widget_def["type"](self.frame, **widget_def["props"])
                widget.grid(row=current_row, column=0, padx=self.PADDING_X, pady=self.PADDING_Y, sticky="nsew")
                setattr(self, widget_def["attr_name"], widget)
                self.frame.grid_rowconfigure(current_row, weight=20)
                widget.bind("<Configure>", self._recalculate_and_apply_wraplengths)

                placeholder_label = CTkLabel(widget, text="Results will appear here...") # Parent is widget directly
                placeholder_label.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
            else:
                # Pass self.frame as the master for these widgets
                widget = widget_def["type"](self.frame, **widget_def["props"])
                widget.grid(row=current_row, column=0, padx=self.PADDING_X, pady=self.PADDING_Y, sticky="ew")
                # Store widget in instance attribute for later reference
                setattr(self, widget_def["attr_name"], widget)
            current_row +=1

        # self.results_frame.update_idletasks() # Removed: results_frame is created on demand
        # self.results_frame.focus_set() # Removed: results_frame is created on demand

    def _create_and_grid_label(self, parent, text, row, column, padx, pady, sticky, justify="left", anchor="w", wraplength=None):
        """Helper to create and grid a CTkLabel."""
        label_props = {"text": text, "justify": justify, "anchor": anchor}
        is_wrappable_label = False
        if wraplength is not None:
            label_props["wraplength"] = wraplength # Set initial wraplength
            is_wrappable_label = True # Mark for dynamic updates
        
        label = CTkLabel(parent, **label_props)
        if is_wrappable_label:
            label.is_wrappable = True # Add the marker attribute
        label.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
        return label

    # UI Update Helper Methods (called by handlers or app_controller)
    # These remain in View as they directly manipulate View's widgets or show dialogs
    def update_event_log_from_controller(self, message, clear_previous=False, scroll_to_top=False):
        if clear_previous:
            self.event_log.delete("0.0", "end")
        self.event_log.insert("end", message)
        if scroll_to_top:
            self.event_log.see("0.0")
        else:
            self.event_log.see("end")

    def clear_query_input(self):
        self.query_input.delete(0, "end")

    def update_status_label(self, message):
        self.label.configure(text=message)

    def show_warning(self, title, message):
        messagebox.showwarning(title=title, message=message)

    def show_info(self, title, message):
        messagebox.showinfo(title=title, message=message)

    def show_error(self, title, message):
        messagebox.showerror(title=title, message=message)

    def _ensure_results_frame_exists(self):
        if hasattr(self, 'results_frame') and self.results_frame.winfo_exists():
            return

        results_frame_row = 4 

        self.results_frame = CustomScrollableFrame( # Use CustomScrollableFrame
            self.frame,
            height=200 
            # label_text removed, CustomScrollableFrame does not have this prop
        )
        self.results_frame.grid(row=results_frame_row, column=0, padx=self.PADDING_X, pady=self.PADDING_Y, sticky="nsew")
        self.frame.grid_rowconfigure(results_frame_row, weight=20) 
        
        self.results_frame.bind("<Configure>", self._recalculate_and_apply_wraplengths)
        # Placeholder is now added in display_search_results to the content_frame
        # self.results_frame.update_idletasks() # update_scrollregion in CustomScrollableFrame handles internal updates

    def display_search_results(self, results_list):
        """Clear existing results and display new ones (list of dicts) in the results_frame."""
        self._ensure_results_frame_exists() # Ensure results_frame is created

        # Call update_idletasks here, after ensuring frame exists and before populating/clearing
        # For CustomScrollableFrame, this might not be strictly needed for the outer frame, but for its content_frame
        content_frame = self.results_frame.get_content_frame()
        content_frame.update_idletasks()

        for widget in content_frame.winfo_children(): # Clear from content_frame
            widget.destroy()

        if not results_list:
            placeholder_label = CTkLabel(content_frame, text="No results to display or search not yet performed.") # Use content_frame
            placeholder_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
            self.results_frame.update_scrollregion() # Update scroll region
            return

        if len(results_list) == 1 and 'message' in results_list[0]:
            message_label = CTkLabel(content_frame, text=results_list[0]['message'], justify="left", anchor="w") # Use content_frame
            message_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
            self.results_frame.update_scrollregion() # Update scroll region
            return

        for i, result_data in enumerate(results_list):
            result_item_frame = CTkFrame(
                content_frame,  # Parent is now the content_frame
                corner_radius=10,
            )
            result_item_frame.grid(row=i, column=0, padx=5, pady=(5 if i==0 else 15), sticky="ew")
            result_item_frame.grid_columnconfigure(0, weight=1)

            current_item_row = 0
            
            id_file_text = f"{result_data.get('id', 'N/A')}. File: {result_data.get('file', 'N/A')}"
            self._create_and_grid_label(result_item_frame, id_file_text, current_item_row, 0, padx=10, pady=(5,2), sticky="ew")
            current_item_row += 1

            distance_text = f"Distance: {result_data.get('distance', float('nan')):.4f}"
            self._create_and_grid_label(result_item_frame, distance_text, current_item_row, 0, padx=10, pady=2, sticky="ew")
            current_item_row += 1

            sentence_text = result_data.get('sentence', 'N/A')
            self._create_and_grid_label(result_item_frame, f"Sentence: {sentence_text}", current_item_row, 0, padx=10, pady=2, sticky="ew", wraplength=self.DEFAULT_MIN_WRAPLENGTH)
            current_item_row += 1

            if result_data.get('context_content'):
                context_header_text = f"---- Context (Page {result_data.get('context_page', 'N/A')}) ----"
                self._create_and_grid_label(result_item_frame, context_header_text, current_item_row, 0, padx=10, pady=(5,0), sticky="ew")
                current_item_row += 1

                self._create_and_grid_label(result_item_frame, result_data['context_content'], current_item_row, 0, padx=10, pady=(0,5), sticky="ew", wraplength=self.DEFAULT_MIN_WRAPLENGTH)
                current_item_row += 1
                
                self._create_and_grid_label(result_item_frame, "---------------------", current_item_row, 0, padx=10, pady=(0,5), sticky="ew")
                current_item_row += 1

            elif result_data.get('context_message'):
                self._create_and_grid_label(result_item_frame, result_data['context_message'], current_item_row, 0, padx=10, pady=5, sticky="ew", wraplength=self.DEFAULT_MIN_WRAPLENGTH)
                current_item_row += 1
        
        self.results_frame.update_scrollregion() # Crucial: update scroll region after adding all items
        self._recalculate_and_apply_wraplengths() # Apply wraplengths
        # self.results_frame.update_idletasks() # Not needed for CustomScrollableFrame outer, scrollregion handles it.
        self.results_frame.canvas.focus_set() # Set focus to the canvas for scrolling

    def _recalculate_and_apply_wraplengths(self, event=None):
        """Recalculates and applies wraplength to all relevant labels in the results_frame."""
        if not hasattr(self, 'results_frame') or not self.results_frame.winfo_exists():
             return
        
        content_frame = self.results_frame.get_content_frame()
        if not content_frame.winfo_exists():
             return

        effective_text_wraplength = self.INITIAL_FALLBACK_WRAPLENGTH
        
        content_frame.update_idletasks() # Ensure width of content_frame is current for calculation

        try:
            scrollable_frame_width = content_frame.winfo_width()

            if scrollable_frame_width > 1:
                padding_and_buffer = 30 + 20 
                calculated_value = scrollable_frame_width - padding_and_buffer
                if calculated_value >= self.DEFAULT_MIN_WRAPLENGTH:
                    effective_text_wraplength = calculated_value
                elif effective_text_wraplength < self.DEFAULT_MIN_WRAPLENGTH: 
                    effective_text_wraplength = self.DEFAULT_MIN_WRAPLENGTH
            elif effective_text_wraplength < self.DEFAULT_MIN_WRAPLENGTH: 
                 effective_text_wraplength = self.DEFAULT_MIN_WRAPLENGTH
        except Exception: # pylint: disable=broad-except
            if effective_text_wraplength < self.DEFAULT_MIN_WRAPLENGTH:
                 effective_text_wraplength = self.DEFAULT_MIN_WRAPLENGTH

        for item_frame in content_frame.winfo_children(): 
            if isinstance(item_frame, CTkFrame):
                is_placeholder = True
                for child in item_frame.winfo_children():
                    if hasattr(child, 'is_wrappable'): 
                        is_placeholder = False
                        break
                if is_placeholder and len(item_frame.winfo_children()) == 1 and isinstance(item_frame.winfo_children()[0], CTkLabel):
                    continue 

                for label in item_frame.winfo_children():
                    if isinstance(label, CTkLabel) and hasattr(label, 'is_wrappable') and label.is_wrappable:
                        label.configure(wraplength=effective_text_wraplength)
                item_frame.update_idletasks() 
        
        content_frame.update_idletasks() 
        self.results_frame.update_scrollregion() # Ensure scroll region is updated after wraplength changes

    # This method is called by the app_controller (App instance via file watcher)
    def update_ui_from_watch(self, message):
        """Update the UI with file system event notifications"""
        self.event_log.insert("end", message + "\n")
        self.event_log.see("end")
        self.update_status_label(message) # Changed from self.label.configure for consistency

    # Methods like clear_log_ui, select_directory_ui, on_index_click_ui, on_query_submit_ui,
    # set_target_directory, handle_index_click, handle_query_submit have been moved to ViewHandlers.

    # Example of a button callback if it were purely UI related
    # def button_callback_ui(self):
    #     self.label.configure(text="Button clicked!") 