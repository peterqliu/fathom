import numpy as np
from index_fragment import SemanticFragmenter
from file_utils import blue, green, red
import time
import os
from parse_mapping import FILE_TYPE_TO_STREAMER
from constants import INDEX_DIR
from config import Config
from sqlite_utils import FilenamesDB, FragmentsDB
from vectorIndex_utils import VectorIndex
import logging
import threading
from model import EmbeddingModel

logger = logging.getLogger(__name__)

# Set tokenizers parallelism before importing any HuggingFace modules
os.environ["TOKENIZERS_PARALLELISM"] = "false"

MAX_CONCURRENT_INDEXING_THREADS = 2
new_work_event = threading.Event() # Global event to signal main loop


def _process_file_internal(file_path: str, file_id: int, vector_idx: VectorIndex, model: EmbeddingModel) -> bool:
    try:
        with FilenamesDB() as fdb, FragmentsDB() as frag_db:

            fragment_indices, fragment_sub_indices, fragment_lengths, fragment_hashes, fragment_embeddings, cluster_memberships, center_embeddings = SemanticFragmenter(filepath=file_path, model=model).process()

            num_fragments_found = len(fragment_hashes) if fragment_hashes is not None else 0

            if fragment_hashes is not None and num_fragments_found > 0:
                if fragment_embeddings is None or len(fragment_embeddings) != num_fragments_found:
                    print(f"Error: Mismatch between number of fragment hashes ({num_fragments_found}) and fragment embeddings ({len(fragment_embeddings) if fragment_embeddings is not None else 0}).")
                    fdb.set_file_status(file_path, 'failed')
                    fdb.commit()
                    return False

                prepared_fragments_data = []
                for i in range(num_fragments_found):
                    current_fragment_hash = fragment_hashes[i]
                    fragment_tuple = (
                        file_id,
                        fragment_indices[i],
                        fragment_sub_indices[i],
                        fragment_lengths[i],
                        0,
                        current_fragment_hash
                    )
                    prepared_fragments_data.append(fragment_tuple)

                if prepared_fragments_data:
                    print(f"Attempting to insert {len(prepared_fragments_data)} fragments into DB for {file_path}...")
                    frag_ids = frag_db.insert(prepared_fragments_data)
                    print(f"Successfully inserted fragments into DB for {file_path}. Received {len(frag_ids) if frag_ids else 'no'} IDs.")

                    if not frag_ids or len(frag_ids) != len(prepared_fragments_data):
                        print(f"Error: Failed to insert all fragments into DB or mismatch in returned IDs. Expected {len(prepared_fragments_data)}, Got {len(frag_ids) if frag_ids else 0}")
                        fdb.set_file_status(file_path, 'failed')
                        fdb.commit()
                        return False

                    valid_embeddings_to_index = []
                    corresponding_frag_ids_for_index = []

                    for i in range(len(frag_ids)):
                        if fragment_embeddings[i] is not None:
                            valid_embeddings_to_index.append(fragment_embeddings[i])
                            corresponding_frag_ids_for_index.append(frag_ids[i])
                        else:
                            print(f"Skipping indexing for fragment {i} (DB ID: {frag_ids[i]}) due to None embedding.")

                    if valid_embeddings_to_index:
                        embeddings_np = np.array(valid_embeddings_to_index)
                        if embeddings_np.ndim == 1:
                             if embeddings_np.size > 0:
                                embeddings_np = embeddings_np.reshape(1, -1)
                             else:
                                print(f"No valid embeddings to convert to 2D numpy array after filtering for {file_path}.")

                        if embeddings_np.size > 0:
                            frag_ids_np = np.array(corresponding_frag_ids_for_index, dtype=np.int64)
                            print(f"Attempting to add {len(frag_ids_np)} embeddings to vector index for {file_path}...")
                            vector_idx.add_with_ids(embeddings_np, frag_ids_np)
                            print(f"Successfully added {len(frag_ids_np)} fragment embeddings to vector index for {file_path}.")
                            print(f"Attempting to save vector index after processing {file_path}...")
                            vector_idx.save_index()
                            print(f"Successfully saved vector index after processing {file_path}.")
                            Config.set_index_updated_flag(True)
                        else:
                            print(f"No fragment embeddings were processed for vector indexing for {file_path} after numpy conversion.")
                    else:
                        print(f"No valid (non-None) fragment embeddings found to add to vector index for {file_path}.")
            else:
                print(f"No fragments found for {file_path}. Nothing to insert or index.")

            fdb.set_file_status(file_path, 'indexed')
            fdb.commit()
            return True

    except Exception as e:
        print(f"Error in _process_file_internal for {file_path}: {str(e)}")
        logger.error(f"Exception in _process_file_internal for {file_path}:", exc_info=True)
        try:
            with FilenamesDB() as fdb_except:
                fdb_except.set_file_status(file_path, 'failed')
                fdb_except.commit()
        except Exception as db_e:
            print(f"Additionally, failed to set file status to 'failed' for {file_path} due to: {db_e}")
        return False


def _processing_thread_task(file_path: str, file_id: int, vector_idx: VectorIndex, model: EmbeddingModel):
    print(f"Starting processing in a new thread for: {file_path} (ID: {file_id})")
    success = _process_file_internal(file_path, file_id, vector_idx, model)
    if success:
        print(green(f"Successfully processed {file_path} in its thread."))
    else:
        print(red(f"Failed to process {file_path} in its thread."))

    new_work_event.set() # Signal main loop that a task finished

def process_file(file_path: str, vector_idx: VectorIndex, model: EmbeddingModel):
    """Launches a thread to process a single file. Assumes file_id exists and status is 'processing'."""
    file_id_to_process = None
    try:
        with FilenamesDB() as fdb: # Get a DB connection to find the file_id
            file_id_to_process = fdb.get_file_id_by_path(file_path)
            # No commit needed here as we are only reading.
            # Status is assumed to be 'processing', set by the main loop.

            if file_id_to_process is None:
                # This can happen if the file record was deleted from the DB
                # between the main loop scheduling it and this function trying to access it.
                print(red(f"Warning: process_file for {file_path} could not find its file_id. The record might have been deleted from DB after scheduling. Skipping item."))
                new_work_event.set() # Signal main loop to re-evaluate state
                return

    except Exception as e:
        print(red(f"Error in process_file DB setup for {file_path}: {e}"))
        new_work_event.set() # Signal main loop to re-evaluate state
        return

    # If file_id was found:
    thread = threading.Thread(target=_processing_thread_task, args=(file_path, file_id_to_process, vector_idx, model))
    thread.daemon = True
    thread.start()

def index_directory(directory_path: str, embedding_model: EmbeddingModel, proportion=0.05):
    print(f"Using index directory: {INDEX_DIR}")
    print(f"Indexing directory: {directory_path}")

    if not embedding_model or not embedding_model.is_ready():
        print(red("Error: Embedding model is not provided or not ready."))
        return

    if not os.path.exists(directory_path):
        print(f"Directory does not exist: {directory_path}")
        return

    if not os.path.isdir(directory_path):
        print(f"Path is not a directory: {directory_path}")
        return

    # vector_idx is initialized in main now
    supported_files_count = 0
    files_newly_queued_count = 0
    skipped_count = 0
    already_queued_count = 0
    processing_at_startup_count = 0 # Files found in 'processing' state

    with FilenamesDB() as fdb:
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_extension = os.path.splitext(file)[1].lower()
                if file_extension in FILE_TYPE_TO_STREAMER:
                    file_path = os.path.normpath(os.path.join(root, file))
                    supported_files_count +=1

                    # Ensure file record exists before trying to get/set status
                    # get_or_create_file_id now doesn't set status.
                    fdb.get_or_create_file_id(file_path) # Ensures record exists
                    fdb.commit() # Commit creation if any

                    status = fdb.get_file_status(file_path)

                    if status == 'indexed':
                        if fdb.is_file_already_indexed(file_path):
                            print(f"File {file_path} is already indexed and up-to-date. Skipping.")
                            skipped_count += 1
                        else:
                            print(f"File {file_path} was indexed, but modified since. Setting to 'queued'.")
                            fdb.set_file_status(file_path, 'queued')
                            files_newly_queued_count +=1
                    elif status == 'failed':
                         print(f"File {file_path} was marked 'failed'. Setting to 'queued'.")
                         fdb.set_file_status(file_path, 'queued')
                         files_newly_queued_count +=1
                    elif status == 'processing':
                        print(f"Warning: File {file_path} found in 'processing' state during startup. Main loop will assess.")
                        processing_at_startup_count +=1
                    elif status == 'queued':
                        print(f"File {file_path} is already queued.")
                        already_queued_count += 1
                    else: # New file (status is None) or some other unexpected status
                         print(f"Setting new or unhandled file {file_path} to 'queued'.")
                         fdb.set_file_status(file_path, 'queued')
                         files_newly_queued_count +=1
        fdb.commit() # Final commit for all status changes in the loop

    print(f"Directory scan complete: {supported_files_count} supported files found.")
    print(f"  - {files_newly_queued_count} newly set to 'queued' (or re-queued).")
    print(f"  - {skipped_count} already indexed and up-to-date.")
    print(f"  - {already_queued_count} were already in 'queued' state.")
    print(f"  - {processing_at_startup_count} found in 'processing' state (will be assessed by main loop).")

    total_initial_queue = files_newly_queued_count + already_queued_count

    if total_initial_queue > 0 or processing_at_startup_count > 0:
        print(blue(f"Signaling main processing loop to start or check for work (Initial queue: {total_initial_queue}, Processing at startup: {processing_at_startup_count})."))
        new_work_event.set() # Signal the main loop to start checking
    elif skipped_count == supported_files_count and supported_files_count > 0:
        print(green("All supported files are already indexed and up-to-date."))
    elif supported_files_count == 0:
        print("No supported files found to index in the directory.")
    else:
        print(blue("No files to queue or process at this time."))

    print(blue("Initial scan and queueing complete. Main loop will manage processing."))
    # The rest of the function (timing, size metrics) is removed as it's misleading now.

# This function will encapsulate the main indexing control loop
def run_indexing_loop(main_model: EmbeddingModel, main_vector_idx: VectorIndex, work_event: threading.Event):
    print(blue("INDEX_LOOP: Entering control loop. Waiting for work signals..."))

    try:
        while True:
            work_event.wait()  # Wait for a signal
            work_event.clear() # Reset the event immediately

            print(blue("INDEX_LOOP: Awakened by event. Checking for work..."))

            with FilenamesDB() as fdb:
                processing_count = fdb.get_processing_count()
                if processing_count is None:
                    print(red("INDEX_LOOP: Error getting processing count from DB. Retrying after delay."))
                    time.sleep(5)
                    work_event.set()
                    continue

                print(f"INDEX_LOOP: Currently {processing_count} files processing.")

                while processing_count < MAX_CONCURRENT_INDEXING_THREADS:
                    next_file = fdb.get_next_queued_file_path()
                    if next_file:
                        print(green(f"INDEX_LOOP: Found queued file '{next_file}'. Setting to 'processing' and starting..."))
                        fdb.set_file_status(next_file, 'processing')
                        fdb.commit()

                        process_file(next_file, main_vector_idx, main_model)
                        processing_count += 1
                    else:
                        print(blue("INDEX_LOOP: No more queued files found in this check cycle."))
                        break

                queued_count = fdb.get_queued_count()
                current_processing_count = fdb.get_processing_count()

                if queued_count == 0 and current_processing_count == 0:
                    print(green("INDEX_LOOP: No queued files and no files processing. Indexing appears complete. Loop will continue to wait for new events."))
                    # Do not break; let it wait for new watcher events or manual triggers.
                else:
                    print(blue(f"INDEX_LOOP: Work remains (Queued: {queued_count}, Processing: {current_processing_count}). Waiting for next event..."))
                    if queued_count > 0 and current_processing_count < MAX_CONCURRENT_INDEXING_THREADS:
                        work_event.set() # Re-signal if there are queued items and free slots

    except KeyboardInterrupt:
        print(red("INDEX_LOOP: Keyboard interrupt received. Shutting down..."))
    except Exception as e:
        print(red(f"INDEX_LOOP: An unexpected error occurred: {e}"))
        logger.error("INDEX_LOOP: Exception in main loop:", exc_info=True)
    finally:
        print(blue("INDEX_LOOP: Exiting."))


if __name__ == "__main__":
    # This block is now for testing index.py directly if needed.
    # The main application (app.py) will call run_indexing_loop in a thread.
    print("Running index.py directly for testing...")

    target_dir = Config.get("target")
    if not target_dir:
        print(red("Error: No target directory configured in constants.py for direct test."))
        exit(1)

    print("Main (test): Initializing EmbeddingModel...")
    test_model = EmbeddingModel()
    while not test_model.is_ready():
        time.sleep(0.1)
    print(green("Main (test): EmbeddingModel is ready."))

    test_vector_idx = VectorIndex()

    # For direct testing, first perform the scan and queue.
    print(f"Main (test): Performing initial scan of {target_dir}...")
    index_directory(target_dir, test_model)

    # Then start the loop.
    # Ensure new_work_event is defined globally in this file as: new_work_event = threading.Event()
    print(f"Main (test): Starting indexing loop with event: {new_work_event}")
    run_indexing_loop(test_model, test_vector_idx, new_work_event)
