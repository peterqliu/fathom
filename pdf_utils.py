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
# print(extract_text_from_pdf('mindsight.pdf'))
# print(extract_text_from_pdf_page('mindsight.pdf', 20))
