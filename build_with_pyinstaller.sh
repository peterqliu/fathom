#!/bin/bash

# Exit on error
set -e

echo "=== Starting build process for standalone macOS app with PyInstaller ==="

# Ensure we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Error: Please activate your virtual environment first:"
    echo "source venv/bin/activate"
    exit 1
fi

# Clean previous builds
echo "=== Cleaning previous builds ==="
rm -rf build dist

# Build the app with PyInstaller in onefile mode to prevent self-spawning issue
echo "=== Building standalone app ==="
pyinstaller --name="MinimalApp" \
            --windowed \
            --debug all \
            --clean \
            --noconfirm \
            --add-data="venv/lib/python3.13/site-packages/customtkinter:customtkinter" \
            app.py

# Clean up build artifacts
echo "=== Cleaning up build artifacts ==="
rm -rf build
rm -rf dist/MinimalApp

echo "=== Build complete! ==="
echo "Your standalone app is available at: dist/MinimalApp.app" 