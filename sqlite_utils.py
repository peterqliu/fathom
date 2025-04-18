import sqlite3
import os
from constants import INDEX_DIR

def init_sqlite_db():
    """Initialize the SQLite database for storing sentences."""
    db_path = os.path.join(INDEX_DIR, 'sentences.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table exists and has the correct schema
    cursor.execute("PRAGMA table_info(sentences)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    # If table doesn't exist or is missing id column, recreate it
    if not columns or 'id' not in column_names:
        # Drop existing table if it exists
        cursor.execute('DROP TABLE IF EXISTS sentences')
        
        # Create table with new schema
        cursor.execute('''
        CREATE TABLE sentences (
            rowid INTEGER PRIMARY KEY,
            path TEXT,
            sentence TEXT,
            id INTEGER
        )
        ''')
        print("Created new sentences table with id column")
    
    conn.commit()
    conn.close()

def get_next_available_id(cursor):
    """Find the next available rowid by checking for NULL paths or next auto-increment."""
    # First check for any NULL paths
    cursor.execute('SELECT MIN(rowid) FROM sentences WHERE path IS NULL')
    null_id = cursor.fetchone()[0]
    
    # Then get the next auto-increment value
    cursor.execute('SELECT MAX(rowid) FROM sentences')
    max_id = cursor.fetchone()[0]
    next_id = (max_id + 1) if max_id is not None else 1
    
    # Return the lower of the two (or next_id if no NULL paths)
    return min(null_id, next_id) if null_id is not None else next_id

def insert_sentences(file_path, sentences, page_indices):
    """Insert sentences for a file into the database, using the lowest available rowid."""
    db_path = os.path.join(INDEX_DIR, 'sentences.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    row_ids = []
    current_rowid = get_next_available_id(cursor)
    
    # Insert each sentence with its page index
    for sentence, page_idx in zip(sentences, page_indices):
        # First try to update any existing NULL path row
        cursor.execute('''
            UPDATE sentences 
            SET path = ?, sentence = ?, id = ?
            WHERE rowid = ? AND path IS NULL
        ''', (file_path, sentence, page_idx, current_rowid))
        
        # If no row was updated (no NULL path at this rowid), insert new row
        if cursor.rowcount == 0:
            cursor.execute('''
                INSERT INTO sentences (rowid, path, sentence, id)
                VALUES (?, ?, ?, ?)
            ''', (current_rowid, file_path, sentence, page_idx))
        
        row_ids.append(current_rowid)
        current_rowid += 1
    
    conn.commit()
    conn.close()
    return row_ids

def get_sentence_by_id(cursor, rowid):
    """Get sentence, path, and page index for a given rowid from the SQLite database."""
    cursor.execute('SELECT path, sentence, id FROM sentences WHERE rowid = ?', (rowid,))
    result = cursor.fetchone()
    if result:
        return {
            'path': result[0],
            'sentence': result[1],
            'id': result[2]
        }
    return None

def get_sentences_by_path(file_path):
    """Retrieve all sentences for a given file path."""
    db_path = os.path.join(INDEX_DIR, 'sentences.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT sentence FROM sentences WHERE path = ? ORDER BY rowid',
        (file_path,)
    )
    sentences = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return sentences

def get_all_sentences():
    """Retrieve all sentences from the database."""
    db_path = os.path.join(INDEX_DIR, 'sentences.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT path, sentence FROM sentences ORDER BY rowid')
    results = cursor.fetchall()
    
    conn.close()
    return results 