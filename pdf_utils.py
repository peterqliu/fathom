from pypdf import PdfReader
from nltk.tokenize import sent_tokenize
# import time # Performance logging import removed


def extract_text_from_pdf_page(pdf_path, pageIndex):
    reader = PdfReader(pdf_path)
    page = reader.pages[pageIndex]  # Adjust for 0-based indexing
    
    # Replace multiple spaces with a single space and add page text
    page_text = ' '.join(page.extract_text().split()).replace('...', '.').replace('..', '.')
    pageSentences = list(filter(overThree, sent_tokenize(page_text)))
    return pageSentences

def get_pdf_num_pages(pdf_path):
    """
    Gets the total number of pages in a PDF document.

    Args:
        pdf_path (str): The path to the PDF file.

    Returns:
        int: The number of pages in the PDF.
    """
    reader = PdfReader(pdf_path)
    return len(reader.pages)

    
def overThree(string):
    return len(string) > 3

def combinePages(before, after):
    return before + " " + after

def combine_short_sentences_with_subindices(sentences_with_subindices, min_length=20):
    """
    Combines short sentences while preserving the original sub-index of the first sentence in a combination.
    
    Args:
        sentences_with_subindices (list): A list of (sentence_text, original_sub_index) tuples.
        min_length (int): The minimum length for a sentence to not be combined.
        
    Returns:
        list: A list of (combined_sentence_text, original_sub_index_of_first_part) tuples.
    """
    if not sentences_with_subindices:
        return []
    
    result = []
    i = 0
    while i < len(sentences_with_subindices):
        current_text, first_sub_idx_in_group = sentences_with_subindices[i]
        
        # Pointer for combining subsequent sentences
        next_item_idx = i + 1
        # Keep combining with next sentences until we reach minimum length or run out of sentences
        while len(current_text) < min_length and next_item_idx < len(sentences_with_subindices):
            next_text, _ = sentences_with_subindices[next_item_idx]
            current_text += " " + next_text
            next_item_idx += 1
        
        result.append((current_text, first_sub_idx_in_group))
        i = next_item_idx # Move main iterator to the start of the next unprocessed sentence
    
    return result

def combine_short_sentences(sentences, min_length=20):
    if not sentences:
        return []
    
    result = []
    i = 0
    
    while i < len(sentences):
        current = sentences[i]
        next_idx = i + 1
        
        # Keep combining with next sentences until we reach minimum length or run out of sentences
        while len(current) < min_length and next_idx < len(sentences):
            current += " " + sentences[next_idx]
            next_idx += 1
        
        result.append(current)
        i = next_idx if next_idx > i + 1 else i + 1
    
    return result

def _process_page_text(sentences_with_subindices_on_page, current_page_actual_index, incoming_fragment_text, incoming_fragment_page_index, incoming_fragment_sub_index):
    """
    Processes sentences from a single page, handling incoming fragments and identifying outgoing ones.

    Args:
        sentences_with_subindices_on_page (list): List of (text, original_sub_idx) for the current page.
        current_page_actual_index (int): The 0-based index of the current page.
        incoming_fragment_text (str): Fragment text from the previous page.
        incoming_fragment_page_index (int): Original page index of the incoming fragment.
        incoming_fragment_sub_index (int): Original sub-index of the incoming fragment.

    Returns:
        tuple: (list_of_processed_sentences, outgoing_fragment_details_tuple)
               list_of_processed_sentences is a list of (sentence_text, page_index, sub_index) tuples.
               outgoing_fragment_details_tuple is (text, page_idx, sub_idx) for the next page.
    """
    processed_sentences_list = []
    process_list = list(sentences_with_subindices_on_page) # Make a mutable copy

    # 1. Handle incoming fragment
    if incoming_fragment_text:
        if process_list: # If current page has content to combine with
            first_sentence_text, _ = process_list[0]
            combined_sentence = incoming_fragment_text + " " + first_sentence_text
            processed_sentences_list.append((combined_sentence, incoming_fragment_page_index, incoming_fragment_sub_index))
            process_list.pop(0) # Consumed the first sentence of the current page
        else: # Current page is empty, add the incoming fragment as is
            processed_sentences_list.append((incoming_fragment_text, incoming_fragment_page_index, incoming_fragment_sub_index))

    # 2. Identify potential new fragment from the *end* of the current page's remaining content
    outgoing_fragment_text = ""
    outgoing_fragment_page_index = -1
    outgoing_fragment_sub_index = -1

    if process_list:
        original_last_text_if_present, original_last_sub_idx_if_present = sentences_with_subindices_on_page[-1]
        # Check if the last item in process_list is indeed the original last sentence of the page
        # (it might not be if the original list was short and parts were consumed by incoming fragment)
        if process_list[-1][0] == original_last_text_if_present and process_list[-1][1] == original_last_sub_idx_if_present:
            if not original_last_text_if_present.strip().endswith(('.', '?', '!')):
                outgoing_fragment_text = original_last_text_if_present
                outgoing_fragment_page_index = current_page_actual_index
                outgoing_fragment_sub_index = original_last_sub_idx_if_present
                process_list.pop() # Remove it from list to be processed now

    # 3. Combine and add remaining sentences on the current page
    if process_list:
        combined_sentences_tuples = combine_short_sentences_with_subindices(process_list)
        for sentence, first_sub_idx in combined_sentences_tuples:
            processed_sentences_list.append((sentence, current_page_actual_index, first_sub_idx))
    
    return processed_sentences_list, (outgoing_fragment_text, outgoing_fragment_page_index, outgoing_fragment_sub_index)

def stream_text_from_pdf(filepath):
    """
    Stream text from a PDF file, yielding sentence, page index, and sub-index within the page.
    Fragments at the end of a page are combined with the beginning of the next page,
    attributing the combined text to the fragment's original page and sub-index.
    
    Args:
        filepath (str): Path to the PDF file
        
    Yields:
        tuple: (sentence_text, page_index, sub_index) for each processed sentence in the PDF.
    """
    try:
        reader = PdfReader(filepath)
        current_fragment_text = ""
        current_fragment_page_index = -1
        current_fragment_sub_index = -1

        for i, _ in enumerate(reader.pages): # Iterate through pages
            raw_sentences_on_page = extract_text_from_pdf_page(filepath, i)
            sentences_with_subindices_on_page = [(text, s_idx) for s_idx, text in enumerate(raw_sentences_on_page)]
            
            # Call the helper to process this page with current fragment state
            processed_list, (new_frag_text, new_frag_page, new_frag_sub) = _process_page_text(
                sentences_with_subindices_on_page,
                i, # current_page_actual_index
                current_fragment_text,
                current_fragment_page_index,
                current_fragment_sub_index
            )
            
            for item in processed_list:
                yield item
            
            # Update fragment state for the next iteration
            current_fragment_text = new_frag_text
            current_fragment_page_index = new_frag_page
            current_fragment_sub_index = new_frag_sub
        
        # After the loop, if there's any remaining fragment (e.g., from the very last page)
        if current_fragment_text:
            yield current_fragment_text, current_fragment_page_index, current_fragment_sub_index
            
    except Exception as e:
        # Consider more specific error logging or re-raising with context if needed
        raise Exception(f"Error streaming text from PDF file '{filepath}': {str(e)}")

def get_sentence_by_indices(filepath, target_page_index, target_sub_index):
    """
    Retrieves a specific sentence from a PDF given its page and sub-index.
    This function simulates the streaming and fragment logic to reconstruct the sentence.

    Args:
        filepath (str): Path to the PDF file.
        target_page_index (int): The 0-based page index of the desired sentence.
        target_sub_index (int): The 0-based sub-index of the sentence on its original page.

    Returns:
        str or None: The text of the sentence if found, otherwise None.
    """
    # total_start_time = time.perf_counter() # Removed
    # print(f"get_sentence_by_indices started for {filepath}, target_pg={target_page_index}, target_sub={target_sub_index}") # Removed

    try:
        # reader_start_time = time.perf_counter() # Removed
        reader = PdfReader(filepath)
        # reader_end_time = time.perf_counter() # Removed
        # print(f"  PdfReader init time: {reader_end_time - reader_start_time:.4f}s") # Removed
        
        num_pages = len(reader.pages)
        
        current_fragment_text = ""
        current_fragment_page_index = -1
        current_fragment_sub_index = -1
        found_sentence = None

        start_page_for_scan = max(0, target_page_index - 1)
        end_page_for_scan = min(target_page_index + 2, num_pages) 

        # print(f"  Revised scan range: from page {start_page_for_scan} to {end_page_for_scan -1}") # Removed
        # loop_start_time = time.perf_counter() # Removed
        for i in range(start_page_for_scan, end_page_for_scan):
            # page_process_start_time = time.perf_counter() # Removed
            # print(f"  Processing page {i}...") # Removed

            # extract_start_time = time.perf_counter() # Removed
            raw_sentences_on_page = extract_text_from_pdf_page(filepath, i)
            # extract_end_time = time.perf_counter() # Removed
            # print(f"    extract_text_from_pdf_page time: {extract_end_time - extract_start_time:.4f}s") # Removed
            
            sentences_with_subindices_on_page = [(text, s_idx) for s_idx, text in enumerate(raw_sentences_on_page)]
            
            # process_page_text_start_time = time.perf_counter() # Removed
            processed_list, (new_frag_text, new_frag_page, new_frag_sub) = _process_page_text(
                sentences_with_subindices_on_page,
                i, # current_page_actual_index
                current_fragment_text,
                current_fragment_page_index,
                current_fragment_sub_index
            )
            # process_page_text_end_time = time.perf_counter() # Removed
            # print(f"    _process_page_text time: {process_page_text_end_time - process_page_text_start_time:.4f}s") # Removed
            
            for text, p_idx, s_idx in processed_list:
                if p_idx == target_page_index and s_idx == target_sub_index:
                    found_sentence = text
                    break 
            
            if found_sentence:
                break 

            current_fragment_text = new_frag_text
            current_fragment_page_index = new_frag_page
            current_fragment_sub_index = new_frag_sub
            
            if i > target_page_index and current_fragment_page_index != target_page_index:
                 # print(f"  Optimization: stopping early after page {i}.") # Removed
                 break
            # page_process_end_time = time.perf_counter() # Removed
            # print(f"  Page {i} processing total time: {page_process_end_time - page_process_start_time:.4f}s") # Removed

        # loop_end_time = time.perf_counter() # Removed
        # print(f"  Loop processing time: {loop_end_time - loop_start_time:.4f}s") # Removed

        if not found_sentence and current_fragment_text and current_fragment_page_index == target_page_index and current_fragment_sub_index == target_sub_index:
            found_sentence = current_fragment_text
            
        # total_end_time = time.perf_counter() # Removed
        # print(f"get_sentence_by_indices total time: {total_end_time - total_start_time:.4f}s for {filepath}") # Removed
        return found_sentence

    except Exception as e:
        print(f"Error in get_sentence_by_indices for '{filepath}' (pg:{target_page_index}, sub:{target_sub_index}): {str(e)}")
        # total_end_time = time.perf_counter() # Removed
        # print(f"get_sentence_by_indices failed in: {total_end_time - total_start_time:.4f}s for {filepath}") # Removed
        return None

# print(extract_text_from_pdf('mindsight.pdf'))
# print(extract_text_from_pdf_page('mindsight.pdf', 20))
