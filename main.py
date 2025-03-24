import sys
import os
import traceback
from view.view import FathomView
from model_service import ModelService
import logging
import json
import faiss
from constants import (
    APP_SUPPORT_PATH, INDEX_DIR, MODELS_DIR, 
    CONSTANTS_DIR, CONFIG_FILE, STORE_FILE,
    ensure_directories
)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def get_app_paths():
    # Create all required directories
    ensure_directories()
    
    return {
        'app_support': APP_SUPPORT_PATH,
        'store_file': STORE_FILE,
        'models_dir': MODELS_DIR,
        'constants_file': CONFIG_FILE,
        'index_dir': INDEX_DIR
    }

def ensure_default_config(constants_file):
    """Initialize default config if it doesn't exist"""
    if not os.path.exists(constants_file):
        import json
        default_config = {
            "targetDirectory": None
        }
        with open(constants_file, 'w') as f:
            json.dump(default_config, f, indent=2)

def main():
    try:
        logger.debug("Starting application...")
        paths = get_app_paths()
        
        # Initialize model service first
        model_service = ModelService(models_dir=paths['models_dir'], store_file=paths['store_file'])
        ensure_default_config(paths['constants_file'])
        
        # Initialize UI
        logger.debug("Starting GUI...")
        app = FathomView(model_service=model_service)
        
        # Start the app
        app.run()
        
    except Exception as e:
        logger.exception("Fatal error in main program")
        with open('crash.log', 'w') as f:
            f.write(f"Error: {str(e)}\n")
            f.write(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()