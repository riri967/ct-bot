import subprocess
import webbrowser
import time
import threading
import os

def open_browser():
    """Open browser after Streamlit starts"""
    time.sleep(3)
    webbrowser.open('http://localhost:8501')

def main():
    # Change to the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("Starting Critical Thinking Study Interface...")
    print("URL: http://localhost:8501")
    
    # Start browser in background
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Run Streamlit
    subprocess.run([
        'streamlit', 'run', 'streamlit_app.py',
        '--server.port', '8501',
        '--server.headless', 'true',
        '--browser.gatherUsageStats', 'false'
    ])

if __name__ == "__main__":
    main()