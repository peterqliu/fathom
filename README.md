# Minimal CustomTkinter App

A minimal macOS application built with CustomTkinter and packaged with PyInstaller.

## Prerequisites

- Python 3.7+
- pip

## Setup

1. Clone this repository
2. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install the required packages:

```bash
pip install -r requirements.txt
```

## Running the App in Development

To run the app in development mode:

```bash
python app.py
```

## Building the App

To build the standalone application:

```bash
./build_with_pyinstaller.sh
```

This will create a standalone application in the `dist` directory and a ZIP archive for easy distribution.

## Development Notes

- The main application code is in `app.py`
- The PyInstaller build script is in `build_with_pyinstaller.sh`

## Customizing

- Modify the UI in `app.py` to add more functionality
- Update PyInstaller settings in `build_with_pyinstaller.sh` to customize the build 