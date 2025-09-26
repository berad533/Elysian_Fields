"""
Elysian Fields - One-Command Startup
Simple script to start everything with a single command
"""

import os
import sys
import subprocess
import time
import threading
from pathlib import Path

def install_dependencies():
    """Quick dependency check and install"""
    print("🔧 Checking dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements_complete.txt"], 
                      check=True, capture_output=True)
        print("✅ Dependencies ready!")
        return True
    except:
        print("⚠️ Some dependencies may need manual installation")
        return True

def start_backend():
    """Start backend in background"""
    print("🚀 Starting backend server...")
    backend_dir = Path("backend")
    if backend_dir.exists():
        process = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=backend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(3)  # Give backend time to start
        return process
    return None

def start_desktop():
    """Start desktop application"""
    print("🖥️ Starting Elysian Scribe...")
    subprocess.run([sys.executable, "elysian_scribe_backend_integrated.py"])

def main():
    """One-command startup"""
    print("🏛️ ELYSIAN FIELDS - Starting Complete System")
    print("=" * 50)
    
    # Install dependencies
    install_dependencies()
    
    # Start backend
    backend_process = start_backend()
    
    if backend_process:
        print("✅ Backend running at http://localhost:5000")
        print("✅ Starting desktop application...")
        
        try:
            # Start desktop app (this will block until app closes)
            start_desktop()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        finally:
            if backend_process:
                backend_process.terminate()
                print("✅ Backend stopped")
    else:
        print("❌ Failed to start backend")
        return 1
    
    print("👋 Elysian Fields session ended")
    return 0

if __name__ == "__main__":
    sys.exit(main())
