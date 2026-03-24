import faiss
import numpy as np
import os
from constants import VECTOR_INDEX_FILE # Assuming VECTOR_INDEX_FILE is in constants

class VectorIndex:
    def __init__(self, index_file_path=VECTOR_INDEX_FILE):
        self.index_file_path = index_file_path
        self.index = self._load_or_initialize_index()

    def _load_or_initialize_index(self):
        if os.path.exists(self.index_file_path):
            print(f"Loading existing FAISS index from {self.index_file_path}...")
            try:
                return faiss.read_index(self.index_file_path)
            except Exception as e:
                print(f"Error loading existing index: {str(e)}. Creating new index...")
                return None # Will be initialized when first data is added
        else:
            print(f"Creating new FAISS index at {self.index_file_path}...")
            return None # Will be initialized when first data is added

    def add_with_ids(self, embeddings: np.ndarray, ids: np.ndarray):
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        
        if self.index is None:
            dimension = embeddings.shape[1]
            base_index = faiss.IndexFlatL2(dimension)
            self.index = faiss.IndexIDMap(base_index)
            print(f"Initialized new FAISS index with dimension {dimension}.")

        self.index.add_with_ids(embeddings.astype(np.float32), ids.astype(np.int64))
        print(f"Added {len(ids)} vectors to index.")

    def delete_with_ids(self, ids_to_delete: np.ndarray):
        if self.index is None:
            print("Index is not initialized. Cannot delete.")
            return 0
        
        if not hasattr(self.index, 'remove_ids'):
            print("The current FAISS index does not support remove_ids. Rebuilding might be necessary for this functionality.")
            return 0

        if ids_to_delete.size == 0:
            print("No IDs provided to delete.")
            return 0
        
        # The FAISS remove_ids function returns the number of elements successfully removed.
        num_actually_removed = self.index.remove_ids(faiss.IDSelectorBatch(ids_to_delete.astype(np.int64)))
        
        return num_actually_removed

    def save_index(self):
        if self.index is not None:
            faiss.write_index(self.index, self.index_file_path)
        else:
            print("Index is not initialized. Nothing to save.")

    def get_ntotal(self):
        if self.index:
            return self.index.ntotal
        return 0

# Example Usage (optional, for testing)
if __name__ == '__main__':
    # Create a dummy index file for testing
    DUMMY_INDEX_FILE = "dummy_vector_index.faiss"
    if os.path.exists(DUMMY_INDEX_FILE):
        os.remove(DUMMY_INDEX_FILE)

    # Test initialization
    vector_idx = VectorIndex(index_file_path=DUMMY_INDEX_FILE)
    print(f"Index total after init: {vector_idx.get_ntotal()}")

    # Test adding vectors
    embeddings1 = np.random.rand(5, 10).astype(np.float32) # 5 vectors, 10 dimensions
    ids1 = np.array([1, 2, 3, 4, 5])
    vector_idx.add_with_ids(embeddings1, ids1)
    print(f"Index total after add1: {vector_idx.get_ntotal()}")
    vector_idx.save_index()

    # Test loading and adding more vectors
    vector_idx_loaded = VectorIndex(index_file_path=DUMMY_INDEX_FILE)
    print(f"Index total after load: {vector_idx_loaded.get_ntotal()}")
    embeddings2 = np.random.rand(3, 10).astype(np.float32)
    ids2 = np.array([6, 7, 8])
    vector_idx_loaded.add_with_ids(embeddings2, ids2)
    print(f"Index total after add2: {vector_idx_loaded.get_ntotal()}")

    # Test deleting vectors
    ids_to_delete = np.array([1, 3, 7])
    removed_count = vector_idx_loaded.delete_with_ids(ids_to_delete)
    print(f"Removed {removed_count} vectors.")
    print(f"Index total after delete: {vector_idx_loaded.get_ntotal()}")
    
    ids_to_delete_non_existent = np.array([100, 101])
    removed_count_non_existent = vector_idx_loaded.delete_with_ids(ids_to_delete_non_existent)
    print(f"Attempted to remove non-existent IDs, removed: {removed_count_non_existent}")
    print(f"Index total after attempting to delete non-existent IDs: {vector_idx_loaded.get_ntotal()}")

    vector_idx_loaded.save_index()

    # Clean up dummy file
    if os.path.exists(DUMMY_INDEX_FILE):
        os.remove(DUMMY_INDEX_FILE)
    print(f"Cleaned up {DUMMY_INDEX_FILE}") 