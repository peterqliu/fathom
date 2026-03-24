import os
import datetime

def get_directory_size(path):
    """Calculate total size of directory in bytes"""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):  # Skip if it's a symbolic link
                total_size += os.path.getsize(fp)
    return total_size

def format_size(size_in_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} TB"

def blue(text):
    """Return text in bright blue ANSI color"""
    return f"\033[94m{text}\033[0m"

def red(text):
    """Return text in bright red ANSI color"""
    return f"\033[91m{text}\033[0m"

def green(text):
    """Return text in bright green ANSI color"""
    return f"\033[92m{text}\033[0m"

def get_last_modified_time(file_path):
    """Get the last modified time of a file as a timestamp"""
    if os.path.exists(file_path):
        return os.path.getmtime(file_path)
    return None

def format_timestamp(timestamp):
    """Convert timestamp to human readable date/time format"""
    if timestamp:
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return "N/A" 