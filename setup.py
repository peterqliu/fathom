from setuptools import setup
import os

# Get the directory where setup.py is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

APP = ['main.py']

# Include both index and model directories
index_files = []
for root, dirs, files in os.walk('index'):
    for file in files:
        full_path = os.path.join(root, file)
        rel_path = os.path.relpath(full_path, 'index')
        index_files.append((os.path.join('index', os.path.dirname(rel_path)), [full_path]))

model_files = []
for root, dirs, files in os.walk('models'):
    for file in files:
        full_path = os.path.join(root, file)
        rel_path = os.path.relpath(full_path, 'models')
        model_files.append((os.path.join('models', os.path.dirname(rel_path)), [full_path]))

DATA_FILES = index_files + model_files

OPTIONS = {
    'alias': True,
    'argv_emulation': False,
    'packages': [
        'tkinter',
        'faiss',
        'requests',
        'sentence_transformers',
        'torch',
        'threading',
        'numpy',
        'tqdm',
        'PIL',
        'transformers',
        'regex',           # Often required by transformers
        'sacremoses',      # Often required by transformers
        'tokenizers',      # Required by transformers
        'huggingface_hub', # Required by transformers
        'scipy'            # Often required by scientific packages
    ],
    'includes': [
        'view',
        'query',
        'model_service',
        'traceback',
        'packaging',
        'filelock',
        'yaml',
        'json',
        'logging',
        'importlib',
        'sqlite3'
    ],
    'frameworks': ['Python'],  # Ensure Python framework is included
    'excludes': ['matplotlib', 'PyQt5', 'PySide2', 'wx'],  # Exclude unnecessary large packages
    'iconfile': None,  # Remove if you don't have an icon
    'plist': {
        'CFBundleName': 'Fathom',
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '1.0',
        'LSMinimumSystemVersion': '10.10',
        'NSHighResolutionCapable': True
    },
    'dist_dir': SCRIPT_DIR
}

setup(
    name="Fathom",
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
