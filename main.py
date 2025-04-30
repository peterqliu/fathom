import sys
import os
import traceback
from view.view import FathomView
from model_service import ModelService
import logging
import json
from constants import (
    APP_SUPPORT_PATH, INDEX_DIR, MODELS_DIR, 
    CONSTANTS_DIR, CONFIG_FILE, STORE_FILE,
    ensure_directories
)

# Get the application support directory for logs
app_support_dir = os.path.expanduser('~/Library/Application Support/Fathom')
os.makedirs(app_support_dir, exist_ok=True)
log_file = os.path.join(app_support_dir, 'debug.log')
crash_log_file = os.path.join(app_support_dir, 'crash.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def get_app_paths():
    logger.debug("Getting application paths...")
    # Create all required directories
    ensure_directories()
    
    paths = {
        'app_support': APP_SUPPORT_PATH,
        'store_file': STORE_FILE,
        'models_dir': MODELS_DIR,
        'constants_file': CONFIG_FILE,
        'index_dir': INDEX_DIR
    }
    
    logger.debug(f"Application paths: {json.dumps(paths, indent=2)}")
    return paths

def ensure_default_config(constants_file):
    """Initialize default config if it doesn't exist"""
    logger.debug(f"Checking config file at: {constants_file}")
    if not os.path.exists(constants_file):
        logger.info("Creating default config file")
        default_config = {
            "targetDirectory": None
        }
        with open(constants_file, 'w') as f:
            json.dump(default_config, f, indent=2)

def main():
    try:
        logger.debug("Starting application...")
        logger.debug(f"Python version: {sys.version}")
        logger.debug(f"Current working directory: {os.getcwd()}")
        logger.debug(f"Application support directory: {app_support_dir}")
        
        paths = get_app_paths()
        
        # Log environment variables that might be relevant
        logger.debug("Environment variables:")
        for var in ['PYTHONPATH', 'PATH', 'HOME']:
            logger.debug(f"{var}: {os.environ.get(var, 'Not set')}")
        
        # Initialize model service first
        logger.debug("Initializing model service...")
        model_service = ModelService(models_dir=paths['models_dir'])
        ensure_default_config(paths['constants_file'])
        
        # Initialize UI
        logger.debug("Starting GUI...")
        app = FathomView(model_service=model_service)
        
        # Start the app
        logger.debug("Running application...")
        app.run()
        
    except Exception as e:
        logger.exception("Fatal error in main program")
        with open(crash_log_file, 'w') as f:
            f.write(f"Error: {str(e)}\n")
            f.write(traceback.format_exc())
            f.write("\n\nEnvironment:\n")
            f.write(f"Python version: {sys.version}\n")
            f.write(f"Current working directory: {os.getcwd()}\n")
            f.write(f"Application support directory: {app_support_dir}\n")
            f.write("\nEnvironment variables:\n")
            for var in ['PYTHONPATH', 'PATH', 'HOME']:
                f.write(f"{var}: {os.environ.get(var, 'Not set')}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()