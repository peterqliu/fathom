import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import os
import nltk
import html2text
nltk.download('punkt')

def clean_text(content):
    """Clean HTML content and return plain text"""
    soup = BeautifulSoup(content, 'html.parser')
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return ' '.join(chunk for chunk in chunks if chunk)

def combine_short_sentences(sentences, min_length=10):
    """Combine sentences that are too short"""
    if not sentences:
        return []
    
    result = []
    i = 0
    
    while i < len(sentences):
        current = sentences[i]
        next_idx = i + 1
        
        while len(current) < min_length and next_idx < len(sentences):
            current += " " + sentences[next_idx]
            next_idx += 1
        
        result.append(current)
        i = next_idx if next_idx > i + 1 else i + 1
    
    return result

def extract_text_from_epub(file_path):
    """
    Extract text from EPUB file, returning sentences and page indices
    """
    try:
        print(f"Opening EPUB file: {file_path}")  # Debug
        book = epub.read_epub(file_path)
        sentences = []
        pageIndex = []  # Keep track of "page" numbers (chapter positions)
        current_page = 0

        # Get all document items
        items = list(book.get_items())
        print(f"Found {len(items)} items in EPUB")  # Debug

        for item in items:
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                try:
                    # Get content as bytes and decode
                    content = item.get_content().decode('utf-8')
                    
                    # Parse HTML
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Remove script and style elements
                    for elem in soup(['script', 'style']):
                        elem.decompose()
                    
                    # Get text and clean it up
                    text = soup.get_text()
                    text = ' '.join(text.split())  # Clean up whitespace
                    
                    # Split into sentences (simple split by periods for now)
                    chapter_sentences = [s.strip() + '.' for s in text.split('.') if s.strip()]
                    
                    sentences.extend(chapter_sentences)
                    pageIndex.extend([current_page] * len(chapter_sentences))
                    current_page += 1
                    
                except Exception as e:
                    print(f"Error processing chapter: {str(e)}")
                    continue

        if not sentences:
            raise ValueError("No text content extracted from EPUB")

        print(f"Successfully extracted {len(sentences)} sentences from {current_page} chapters")
        return sentences, pageIndex

    except Exception as e:
        print(f"Failed to process EPUB: {str(e)}")
        raise

def extract_text_from_mobi(file_path):
    """
    For MOBI files, convert to EPUB first using calibre's ebook-convert
    If conversion isn't possible, raise an informative error
    """
    try:
        # You might want to implement MOBI-specific handling here
        # For now, suggest using Calibre for conversion
        raise NotImplementedError(
            "MOBI format requires conversion to EPUB first. "
            "Please use Calibre's ebook-convert tool: "
            "ebook-convert input.mobi output.epub"
        )
    except Exception as e:
        raise Exception(f"Error processing MOBI file: {str(e)}")

def process_ebook(filepath):
    """
    Process an ebook file and return sentences with page indices.
    
    Returns:
        tuple: (sentences list, page indices list)
    """
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    if ext == '.epub':
        return extract_text_from_epub(filepath)
    elif ext == '.mobi':
        return extract_text_from_mobi(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Parse ebook content with page tracking')
    parser.add_argument('filepath', help='Path to the ebook file')
    args = parser.parse_args()
    
    try:
        sentences, page_indices = process_ebook(args.filepath)
        for i, (sentence, page) in enumerate(zip(sentences, page_indices)):
            print(f"\nSentence {i+1} (Page {page+1}):")
            print("----------------------------------------")
            print(sentence)
            print("----------------------------------------")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()