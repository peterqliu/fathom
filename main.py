import subprocess
import threading
import time
import os
import sys
from dotenv import load_dotenv
from rich.console import Console
import tkinter as tk
from view import FathomView

console = Console()

def start_model_server():
    """Start the model server in a separate process"""
    try:
        # Print working directory and check if file exists
        console.print(f"Current directory: {os.getcwd()}")
        if not os.path.exists('model_server.py'):
            console.print("[red]Error: model_server.py not found in current directory[/red]")
            return None

        console.print("Starting model server...")
        
        # Start the process with output streaming
        process = subprocess.Popen(
            [sys.executable, 'model_server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,  # Line buffered
            env=os.environ.copy()  # Explicitly pass environment variables
        )

        # Start threads to monitor output
        def stream_output(stream, prefix):
            for line in stream:
                console.print(f"[dim]{prefix}:[/dim] {line.strip()}")

        threading.Thread(target=stream_output, args=(process.stdout, "SERVER"), daemon=True).start()
        threading.Thread(target=stream_output, args=(process.stderr, "SERVER ERROR"), daemon=True).start()

        # Give the process a moment to fail fast if there's an obvious error
        time.sleep(2)
        if process.poll() is not None:
            console.print(f"[red]Server failed to start. Exit code: {process.poll()}[/red]")
            # Get any final output
            stdout, stderr = process.communicate()
            if stdout:
                console.print("[yellow]Server output:[/yellow]\n" + stdout)
            if stderr:
                console.print("[red]Server errors:[/red]\n" + stderr)
            return None

        return process

    except Exception as e:
        console.print(f"[red]Error starting model server: {str(e)}[/red]")
        console.print(f"[red]Error type: {type(e).__name__}[/red]")
        import traceback
        console.print("[red]" + traceback.format_exc() + "[/red]")
        return None

def wait_for_server(timeout=60):  # Increased timeout
    """Wait for the server to be ready"""
    console.print("Waiting for model server to initialize...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            import requests
            response = requests.get('http://localhost:5000/health', timeout=1)
            if response.status_code == 200:
                console.print("[green]Server is ready![/green]")
                return True
        except requests.exceptions.RequestException:
            # Print a waiting indicator
            elapsed = int(time.time() - start_time)
            console.print(f"Waiting for server... ({elapsed}s)", end='\r')
            time.sleep(2)  # Longer delay between checks
    
    # If we get here, server didn't start in time
    console.print("\n[yellow]Server startup timed out. Checking server process...[/yellow]")
    return False

def run_query(query):
    """Run a query using query.py"""
    try:
        result = subprocess.run([sys.executable, 'query.py', query], 
                              capture_output=True, 
                              text=True)
        return result.stdout
    except Exception as e:
        return f"Error running query: {str(e)}"

def main():
    app = FathomView()
    app.run()

if __name__ == "__main__":
    main()