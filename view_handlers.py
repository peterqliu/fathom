import os
import constants
from tkinter import filedialog # For askdirectory
from query import search_index, extract_page_from_file
from index import index_directory

class ViewHandlers:
    def __init__(self, view_instance):
        self.view = view_instance # This is the View object from view.py

    # UI Event Handlers - these will be assigned to widget commands in View
    def clear_log_ui(self):
        self.view.event_log.delete("0.0", "end")
        self.view.update_status_label("Event log cleared")

    def select_directory_ui(self):
        initial_dir = constants.Config.getTargetDirectory()
        directory = filedialog.askdirectory(initialdir=initial_dir)
        if directory:
            self._set_target_directory(directory)
            self.view.update_status_label(f"Directory set to: {directory}")

    def on_index_click_ui(self):
        self._handle_index_click()

    def on_query_submit_ui(self, event=None): # event=None allows direct calls if needed
        query = self.view.query_input.get()
        self._handle_query_submit(query)

    # Core Logic Methods (previously controller methods)
    # Made "private" by convention as they are typically called by the UI handlers above
    def _set_target_directory(self, directory):
        constants.Config.setTargetDirectory(directory)

    def _handle_index_click(self):
        target_dir = constants.Config.getTargetDirectory()
        if not target_dir:
            self.view.show_warning(title="Directory Not Set", message="Please set a target directory first.")
            return
        try:
            index_directory(target_dir)
            self.view.show_info(title="Indexing Complete", message=f"Successfully indexed directory: {target_dir}")
        except Exception as e:
            self.view.show_error(title="Indexing Error", message=f"Error indexing directory {target_dir}: {str(e)}")

    def _handle_query_submit(self, query):
        if query:
            try:
                self.view.update_status_label(f"Searching for: '{query}'...")

                results = search_index(query)
                
                processed_results = [] 

                if results:
                    self.view.update_status_label(f"Found {len(results)} results for '{query}'.")
                    target_dir_for_context = constants.Config.getTargetDirectory()

                    for i, result_data in enumerate(results, 1):
                        result_dict = {
                            'id': i,
                            'file': result_data.get('file', 'N/A'),
                            'distance': result_data.get('distance', float('nan')),
                            'sentence': result_data.get('sentence', 'N/A'),
                            'context_page': None,
                            'context_content': None,
                            'context_message': None # For errors or status messages about context
                        }

                        file = result_dict['file']
                        result_page_index = result_data.get('indices', None) # Keep using original result_data for this
                        result_dict['context_page'] = result_page_index

                        if file != 'N/A' and result_page_index is not None and target_dir_for_context:
                            full_file_path = os.path.join(target_dir_for_context, file)
                            if os.path.exists(full_file_path):
                                try:
                                    page_content = extract_page_from_file(full_file_path, result_page_index)
                                    if page_content:
                                        result_dict['context_content'] = page_content.strip()
                                    else:
                                        result_dict['context_message'] = "Context: Could not extract content for this page (page might be blank or extraction failed)."
                                except ValueError as ve:
                                    result_dict['context_message'] = f"Context: {str(ve)}"
                                except Exception as e_context:
                                    result_dict['context_message'] = f"Context: Error extracting page content: {str(e_context)}"
                            else:
                                result_dict['context_message'] = f"Context: File not found at {full_file_path}"
                        elif not target_dir_for_context and file != 'N/A' and result_page_index is not None:
                            result_dict['context_message'] = "Context: Target directory not set, cannot retrieve page content."
                        else:
                            result_dict['context_message'] = "Context: Not available (file, page index, or target directory missing)."
                        
                        processed_results.append(result_dict)
                    
                else:
                    self.view.update_status_label(f"No results found for '{query}'.")
                    processed_results.append({'message': f"No results found for '{query}'."})
                
                self.view.display_search_results(processed_results)

            except Exception as e:
                self.view.update_status_label(f"Error during search: {str(e)}")
                # Pass a list with a single dictionary for the error message
                self.view.display_search_results([{'message': f"Error searching index for '{query}':\n{str(e)}"}])
            finally:
                self.view.clear_query_input() 