from pypdf import PdfReader
from nltk.tokenize import sent_tokenize


def extract_text_from_pdf_page(reader, pageIndex):
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

def extract_text_from_pdf(filepath):
    """
    Extract text from all pages of a PDF file.
    
    Args:
        filepath (str): Path to the PDF file
        
    Returns:
        str: Extracted text from all pages
    """
    try:
        # Create a PDF reader object
        reader = PdfReader(filepath)
        pageIndex = []
        sentences = []
        currentFragment = ""
        # Extract text from all pages
        text = ""
        for i, page in enumerate(reader.pages):

            pageSentences = extract_text_from_pdf_page(reader, i)
            # Prepend any existing fragment to the first sentence of current page
            if currentFragment and len(currentFragment) > 0 and pageSentences:
                pageSentences[0] = currentFragment + " " + pageSentences[0]
                pageSentences = pageSentences[1:]  # Remove first element after combining
                currentFragment = ""
            
            # Handle potential sentence fragments
            if pageSentences and len(pageSentences) > 0:
                currentFragment = pageSentences[-1]
                pageSentences = pageSentences[:-1]
            
            # Add each sentence to sentences array and track page index
            pageSentences = combine_short_sentences(pageSentences)
            for sentence in pageSentences:
                sentences.append(sentence)
                pageIndex.append(i)  

        return sentences, pageIndex
    
    except Exception as e:
        raise Exception(f"Error reading PDF file: {str(e)}") 
    
def overThree(string):
    return len(string) > 3

def combinePages(before, after):
    return before + " " + after

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

def stream_text_from_pdf(filepath):
    """
    Stream text from a PDF file, yielding one sentence and its page index at a time.
    
    Args:
        filepath (str): Path to the PDF file
        
    Yields:
        tuple: (sentence, page_index) for each sentence in the PDF
    """
    try:
        reader = PdfReader(filepath)
        currentFragment = ""
        
        for i, page in enumerate(reader.pages):
            pageSentences = extract_text_from_pdf_page(reader, i)
            
            # Prepend any existing fragment to the first sentence of current page
            if currentFragment and len(currentFragment) > 0 and pageSentences:
                pageSentences[0] = currentFragment + " " + pageSentences[0]
                pageSentences = pageSentences[1:]  # Remove first element after combining
                currentFragment = ""
            
            # Handle potential sentence fragments
            if pageSentences and len(pageSentences) > 0:
                currentFragment = pageSentences[-1]
                pageSentences = pageSentences[:-1]
            
            # Combine short sentences and yield each one with its page index
            pageSentences = combine_short_sentences(pageSentences)
            for sentence in pageSentences:
                yield sentence, i
    
    except Exception as e:
        raise Exception(f"Error reading PDF file: {str(e)}")

# print(extract_text_from_pdf('mindsight.pdf'))
# print(extract_text_from_pdf_page('mindsight.pdf', 20))
