from setuptools import setup
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('py2app')
logger.setLevel(logging.DEBUG)

APP = ['main.py']
DATA_FILES = []

OPTIONS = {
    'argv_emulation': False,
    'packages': [
        'tkinter',
        'rich',
        'certifi',
        'charset_normalizer',
        'urllib3',
        'questionary',
        'prompt_toolkit',
        'wcwidth',
        'pygments',
        'mdurl'
    ],
    'includes': ['view'],
    'excludes': ['test'],
    'plist': {
        'CFBundleName': 'Fathom',
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '1.0',
        'LSMinimumSystemVersion': '10.10',
    },
    'semi_standalone': False,  # Add this to create a full standalone app
    'site_packages': True     # Include site-packages
}

print("Starting setup process...")  # Add explicit print statement

setup(
    name="Fathom",
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

print("Setup process completed")  # Add explicit print statement
