import sys
import os
import traceback
from view.view import FathomView
from model_service import ModelService
import logging

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
    if getattr(sys, 'frozen', False):
        # We are running in a bundle
        app_support = os.path.expanduser('~/Library/Application Support/Fathom')
        # Create the directory if it doesn't exist
        os.makedirs(app_support, exist_ok=True)
        store_file = os.path.join(app_support, 'index')
        # Add models directory within Application Support
        models_dir = os.path.join(app_support, 'models')
        constants_dir = os.path.join(app_support, 'constants')
        constants_file = os.path.join(constants_dir, 'config.json')
    else:
        # We are running in a normal Python environment
        app_support = "."
        store_file = "content_store.json"
        models_dir = "models"
        constants_dir = "constants"
        constants_file = os.path.join(constants_dir, 'config.json')
    
    # Create directories
    for directory in [models_dir, constants_dir]:
        os.makedirs(directory, exist_ok=True)
    
    return {
        'app_support': app_support,
        'store_file': store_file,
        'models_dir': models_dir,
        'constants_file': constants_file
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