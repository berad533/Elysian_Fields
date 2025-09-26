"""
Elysian Fields - Ultimate One-Command Startup
Foolproof script that handles everything
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path

def main():
    print("🏛️ ELYSIAN FIELDS - Ultimate Startup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("backend").exists():
        print("❌ Backend directory not found!")
        print("   Please run this script from the ElysianFields root directory")
        return 1
    
    # Install dependencies
    print("🔧 Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements_complete.txt"], 
                      check=True, capture_output=True)
        print("✅ Dependencies installed!")
    except:
        print("⚠️ Some dependencies may need manual installation")
    
    # Start backend
    print("🚀 Starting backend server...")
    backend_process = None
    
    try:
        backend_process = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=Path("backend"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a moment for backend to start
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
        print("   (Backend will continue running in the background)")
        print("   (Press Ctrl+C to stop everything)")
        
        # Start desktop app (this blocks until app closes)
        desktop_process = subprocess.run([sys.executable, "elysian_scribe_backend_integrated.py"])
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Clean up backend process
        if backend_process:
            print("🛑 Stopping backend server...")
            backend_process.terminate()
            backend_process.wait()
            print("✅ Backend stopped")
    
    print("👋 Elysian Fields session ended")
    return 0

if __name__ == "__main__":
    sys.exit(main())
