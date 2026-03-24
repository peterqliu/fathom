import sqlite3
import os
from constants import INDEX_DIR
import time
from file_utils import get_last_modified_time, red
import numpy as np

def init_sqlite_db(table_name, columns=None):
    """Initialize the SQLite database with a table of specified name and columns.
    
    Args:
        table_name (str): Name of the table to create/check
        columns (list): List of column definitions in SQL format, e.g. 
            ['id INTEGER PRIMARY KEY', 'path TEXT', 'sentence TEXT']
    """
    if columns is None:
        print(red(f"No columns provided for table {table_name}"))
        return

    
    db_path = os.path.join(INDEX_DIR, table_name + '.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table exists and has the correct schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = cursor.fetchall()
    
    # If table doesn't exist or schema doesn't match, recreate it
    if not existing_columns or len(existing_columns) != len(columns):
        # Drop existing table if it exists
        cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
        
        # Create table with new schema
        create_table_sql = f'''
        CREATE TABLE {table_name} (
            {', '.join(columns)}
        )
        '''
        cursor.execute(create_table_sql)
        print(f"Created new {table_name} table with columns: {', '.join(columns)}")
    
    conn.commit()
    conn.close()


def get_or_create_file_id(file_path: str, last_indexed: int = None) -> int:
    """
    Retrieves the file_id for a given file_path from the filenames table.
    If the file_path does not exist, it inserts a new entry and returns the new file_id.
    Updates lastIndexed timestamp if the file already exists.

    Args:
        file_path (str): The path to the file.
        last_indexed (int, optional): The timestamp of the last indexing. Defaults to current time.

    Returns:
        int: The file_id for the given file_path.
    """
    if last_indexed is None:
        last_indexed = int(time.time())

    db_path = os.path.join(INDEX_DIR, 'filenames.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT file_id FROM filenames WHERE path = ?", (file_path,))
    result = cursor.fetchone()
    
    if result:
        file_id = result[0]
        # Update lastIndexed for existing file
        cursor.execute("UPDATE filenames SET lastIndexed = ? WHERE file_id = ?", (last_indexed, file_id))
    else:
        cursor.execute("INSERT INTO filenames (path, lastIndexed) VALUES (?, ?)", (file_path, last_indexed))
        file_id = cursor.lastrowid # Get the id of the newly inserted row
        
    conn.commit()
    conn.close()
    return file_id


def get_next_rowid(cursor) -> int:
    """Gets the next available rowid for the sentences table."""
    cursor.execute('SELECT MAX(rowid) FROM sentences')
    max_id = cursor.fetchone()[0]
    return (max_id + 1) if max_id is not None else 1

def insert_sentences(file_id: int, page_and_sub_indices: list[tuple[int, int]]) -> list[int]:
    """Insert sentence metadata (file_id, page index, and sub_index) into the database."""
    db_path = os.path.join(INDEX_DIR, 'sentences.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    row_ids = []
    # Get the starting rowid for this batch of insertions. 
    # We need to lock the table or handle concurrency if multiple processes write simultaneously.
    # For now, assuming single writer or external locking for simplicity.
    current_rowid_start = get_next_rowid(cursor) 
    
    inserts = []
    current_rowid_offset = 0
    for page_idx, sub_idx in page_and_sub_indices:
        actual_rowid = current_rowid_start + current_rowid_offset
        inserts.append((actual_rowid, file_id, page_idx, sub_idx))
        row_ids.append(actual_rowid)
        current_rowid_offset += 1
            
    if inserts:
        cursor.executemany('''
            INSERT INTO sentences (rowid, file_id, id, sub_index)
            VALUES (?, ?, ?, ?)
        ''', inserts)
    
    conn.commit()
    conn.close()
    return row_ids

def get_indices_by_rowid(rowid: int) -> dict | None:
    """Get file path, page index, and sub_index for a given rowid from the SQLite databases."""
    # First, get file_id, page_id (id), and sub_index from sentences.db
    s_db_path = os.path.join(INDEX_DIR, 'sentences.db')
    conn_s = sqlite3.connect(s_db_path)
    cursor_s = conn_s.cursor()
    
    cursor_s.execute('SELECT file_id, id, sub_index FROM sentences WHERE rowid = ?', (rowid,))
    sentence_result = cursor_s.fetchone()
    conn_s.close() # Close connection to sentences.db
    
    if not sentence_result:
        return None
        
    file_id, page_id, sub_index = sentence_result
    
    # Next, get the path from filenames.db using the file_id
    f_db_path = os.path.join(INDEX_DIR, 'filenames.db')
    conn_f = sqlite3.connect(f_db_path)
    cursor_f = conn_f.cursor()
    
    cursor_f.execute('SELECT path FROM filenames WHERE file_id = ?', (file_id,))
    path_result = cursor_f.fetchone()
    conn_f.close() # Close connection to filenames.db
    
    if not path_result:
        # This case should ideally not happen if data is consistent
        print(red(f"Error: file_id {file_id} found in sentences.db but no corresponding path in filenames.db for rowid {rowid}."))
        return None
        
    path = path_result[0]
    
    return {
        'path': path,
        'id': page_id,
        'sub_index': sub_index
    }

# def get_page_and_sub_indices_by_path(file_path):
#     """Retrieve all page and sub-indices for a given file path."""
#     db_path = os.path.join(INDEX_DIR, 'sentences.db')
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()
    
#     cursor.execute(
#         'SELECT id, sub_index FROM sentences WHERE path = ? ORDER BY rowid',
#         (file_path,)
#     )
#     indices = [(row[0], row[1]) for row in cursor.fetchall()]
    
#     conn.close()
#     return indices

# def get_all_paths_page_and_sub_indices():
#     """Retrieve all paths, page indices, and sub-indices from the database."""
#     db_path = os.path.join(INDEX_DIR, 'sentences.db')
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()
    
#     cursor.execute('SELECT path, id, sub_index FROM sentences ORDER BY rowid')
#     results = cursor.fetchall() # Returns list of (path, id, sub_index) tuples
    
#     conn.close()
#     return results

def is_file_already_indexed(file_path):
    """
    Check if a file is already indexed and up-to-date.
    
    Compares the file's last modified time with the lastIndexed timestamp
    in the filenames.db database. Returns True if the file is already indexed
    and has not been modified since the last indexing.
    
    Args:
        file_path (str): Path to the file to check
        
    Returns:
        bool: True if the file is already indexed and up-to-date, False otherwise
    """
    # Check if file exists
    if not os.path.exists(file_path):
        return False
    
    # Get the file's last modified time
    last_modified = get_last_modified_time(file_path)
    
    # Connect to the filenames database
    db_path = os.path.join(INDEX_DIR, 'filenames.db')
    if not os.path.exists(db_path):
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the file is in the database
    cursor.execute('SELECT lastIndexed FROM filenames WHERE path = ?', (file_path,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        # File is in database, check if it's been modified since last indexing
        last_indexed = result[0]
        return last_indexed > last_modified
    
    # File not in database
    return False 

def get_file_id_by_path(file_path: str) -> int | None:
    """Retrieves the file_id for a given file_path from the filenames table."""
    db_path = os.path.join(INDEX_DIR, 'filenames.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM filenames WHERE path = ?", (file_path,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None

def remove_filename(file_path):
    """Remove a file entry from the filenames table.

    Args:
        file_path (str): Path to the file to remove.
    """
    db_path = os.path.join(INDEX_DIR, 'filenames.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM filenames WHERE path = ?', (file_path,))

    conn.commit()
    conn.close()

def remove_sentences(file_path: str) -> np.ndarray:
    """Remove all sentences for a given file path from the database.
    
    Args:
        file_path (str): Path to the file whose sentences are to be removed.

    Returns:
        numpy.ndarray: An array of rowids that were deleted. Empty if no rows found.
    """
    file_id = get_file_id_by_path(file_path)
    if file_id is None:
        print(f"No file_id found for path '{file_path}'. Cannot remove sentences.")
        return np.array([], dtype=np.int64)

    db_path = os.path.join(INDEX_DIR, 'sentences.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # First, select the rowids of the sentences to be deleted
    cursor.execute('SELECT rowid FROM sentences WHERE file_id = ?', (file_id,))
    rows_to_delete = cursor.fetchall()
    deleted_rowids = np.array([row[0] for row in rows_to_delete], dtype=np.int64)
    
    if deleted_rowids.size > 0: # Check if there are any IDs to delete
        # Then, delete the sentences
        cursor.execute('DELETE FROM sentences WHERE file_id = ?', (file_id,))
        conn.commit()
        print(f"Deleted {len(deleted_rowids)} sentences for file_id {file_id} (path: '{file_path}') from SQLite.")
    else:
        print(f"No sentences found in SQLite for file_id {file_id} (path: '{file_path}') to delete.")
    
    conn.close()
    return deleted_rowids 

def rename_file(old_path: str, new_path: str):
    """Rename a file's path in filenames.db and updates its lastIndexed timestamp.

    Args:
        old_path (str): The original file path.
        new_path (str): The new file path.
    """
    # Path renaming and timestamp update now only happens in filenames.db
    filenames_db_path = os.path.join(INDEX_DIR, 'filenames.db')
    conn_filenames = sqlite3.connect(filenames_db_path)
    cursor_filenames = conn_filenames.cursor()
    try:
        current_timestamp = int(time.time())
        # We assume old_path uniquely identifies the record to update its path to new_path.
        cursor_filenames.execute("UPDATE filenames SET path = ?, lastIndexed = ? WHERE path = ?", 
                                 (new_path, current_timestamp, old_path))
        conn_filenames.commit()
        if cursor_filenames.rowcount > 0:
            print(f"Updated path in filenames.db from '{old_path}' to '{new_path}' and set lastIndexed.")
        else:
            print(f"No entry found in filenames.db for old_path '{old_path}'. Nothing renamed.")
    except sqlite3.Error as e:
        print(f"Error updating filenames.db for rename from '{old_path}' to '{new_path}': {e}")
    finally:
        conn_filenames.close()

