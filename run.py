"""
Elysian Fields - Ultimate One Command
Starts everything with a single command
"""

import os
import sys
import subprocess
import time
import threading
from pathlib import Path

def main():
    print("🏛️ ELYSIAN FIELDS - Starting Complete System")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("backend").exists():
        print("❌ Please run this from the ElysianFields root directory")
        return 1
    
    # Start backend in background
    print("🚀 Starting backend server...")
    backend_process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=Path("backend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for backend to start
    print("⏳ Waiting for backend to start...")
    time.sleep(5)
    
    # Check if backend is running
    try:
        import requests
        response = requests.get("http://localhost:5000/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running at http://localhost:5000")
        else:
            print("⚠️ Backend may not be fully ready yet")
    except:
        print("⚠️ Backend is starting up...")
    
    # Start desktop app
    print("🖥️ Starting desktop application...")
    print("   (Backend running in background)")
    print("   (Press Ctrl+C to stop everything)")
    
    try:
        # Start desktop app (this blocks until app closes)
        subprocess.run([sys.executable, "elysian_scribe_backend_integrated.py"])
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        # Clean up backend
        if backend_process:
            print("🛑 Stopping backend server...")
            backend_process.terminate()
            backend_process.wait()
            print("✅ Backend stopped")
    
    print("👋 Elysian Fields session ended")
    return 0

if __name__ == "__main__":
    sys.exit(main())
