from nltk.tokenize import sent_tokenize
import docx
from striprtf.striprtf import rtf_to_text

def overThree(string):
    return len(string) > 3

def combine_short_sentences(sentences, min_length=20):
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

def extract_text_from_txt(filepath):
    """
    Extract text from a plain text file.
    """
    try:
        # Read file with proper encoding handling
        with open(filepath, 'r', encoding='utf-8-sig') as file:  # utf-8-sig handles BOM
            text = file.read()
        
        # Handle escape sequences and normalize line breaks
        text = text.encode('unicode_escape').decode('unicode_escape')  # Handle escape sequences
        text = text.replace('\\n', '\n').replace('\\r', '\r')  # Convert explicit \n to actual linebreaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')  # Normalize all line endings to \n
        
        # Split into sentences, handling line breaks as potential sentence boundaries
        paragraphs = text.split('\n\n')  # Split on double line breaks
        raw_sentences = []
        for para in paragraphs:
            para = para.strip()
            if para:  # Skip empty paragraphs
                raw_sentences.extend(sent_tokenize(para))
        
        sentences = list(filter(overThree, raw_sentences))
        sentences = combine_short_sentences(sentences)
        
        # For txt files, we'll use paragraph numbers as "pages"
        pageIndex = [i//10 for i in range(len(sentences))]  # Group every 10 sentences as one "page"
        
        return sentences, pageIndex
    except UnicodeDecodeError:
        # If UTF-8 fails, try with different encodings
        encodings = ['latin-1', 'cp1252', 'ascii']
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as file:
                    text = file.read()
                    # ... (repeat the same text processing as above)
                break
            except UnicodeDecodeError:
                continue
        raise  # If all encodings fail, raise the original error

def extract_text_from_docx(filepath):
    """
    Extract text from a DOCX file.
    """
    try:
        doc = docx.Document(filepath)
        sentences = []
        pageIndex = []
        current_page = 0
        
        for para in doc.paragraphs:
            if para.text.strip():
                para_sentences = sent_tokenize(para.text)
                para_sentences = list(filter(overThree, para_sentences))
                para_sentences = combine_short_sentences(para_sentences)
                
                sentences.extend(para_sentences)
                pageIndex.extend([current_page] * len(para_sentences))
            
            # Increment page counter every few paragraphs
            if len(sentences) - (current_page * 10) >= 10:
                current_page += 1
        
        return sentences, pageIndex
    
    except Exception as e:
        raise Exception(f"Error reading DOCX file: {str(e)}")

def extract_text_from_rtf(filepath):
    """
    Extract text from an RTF file.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            rtf_text = file.read()
        
        # Convert RTF to plain text
        plain_text = rtf_to_text(rtf_text)
        
        # Split into sentences
        raw_sentences = sent_tokenize(plain_text)
        sentences = list(filter(overThree, raw_sentences))
        sentences = combine_short_sentences(sentences)
        
        # Group sentences into "pages"
        pageIndex = [i//10 for i in range(len(sentences))]
        
        return sentences, pageIndex
    
    except Exception as e:
        raise Exception(f"Error reading RTF file: {str(e)}")

def extract_text_from_doc(filepath):
    """
    Extract text from a DOC file.
    Note: This requires antiword to be installed on the system
    """
    try:
        import subprocess
        
        # Use antiword to convert doc to text
        result = subprocess.run(['antiword', filepath], capture_output=True, text=True)
        text = result.stdout
        
        # Split into sentences
        raw_sentences = sent_tokenize(text)
        sentences = list(filter(overThree, raw_sentences))
        sentences = combine_short_sentences(sentences)
        
        # Group sentences into "pages"
        pageIndex = [i//10 for i in range(len(sentences))]
        
        return sentences, pageIndex
    
    except FileNotFoundError:
        raise Exception("antiword not found. Please install antiword to process .doc files")
    except Exception as e:
        raise Exception(f"Error reading DOC file: {str(e)}")