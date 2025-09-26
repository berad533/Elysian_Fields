"""
Elysian Fields - Complete System Startup Script
Handles dependency installation, backend startup, and desktop app launch
"""

import os
import sys
import subprocess
import time
import threading
import webbrowser
from pathlib import Path

class ElysianFieldsLauncher:
    def __init__(self):
        self.backend_process = None
        self.backend_url = "http://localhost:5000"
        self.backend_ready = False
        
    def install_dependencies(self):
        """Install all required dependencies"""
        print("🔧 Installing Dependencies...")
        print("=" * 50)
        
        # Core dependencies
        dependencies = [
            "Flask",
            "Flask-CORS", 
            "Flask-SQLAlchemy",
            "Werkzeug",
            "Pillow",
            "pytesseract",
            "opencv-python",
            "pandas",
            "python-dotenv",
            "requests",
            "folium",
            "googlemaps",
            "customtkinter"
        ]
        
        for dep in dependencies:
            try:
                print(f"Installing {dep}...")
                subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                             check=True, capture_output=True)
                print(f"✅ {dep} installed")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install {dep}: {e}")
                return False
        
        print("✅ All dependencies installed successfully!")
        return True
    
    def check_backend_health(self):
        """Check if backend is running and healthy"""
        try:
            import requests
            response = requests.get(f"{self.backend_url}/api/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def start_backend(self):
        """Start the Flask backend server"""
        print("\n🚀 Starting Backend Server...")
        print("=" * 50)
        
        # Change to backend directory
        backend_dir = Path("backend")
        if not backend_dir.exists():
            print("❌ Backend directory not found!")
            return False
        
        try:
            # Start backend process
            self.backend_process = subprocess.Popen(
                [sys.executable, "app.py"],
                cwd=backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for backend to start
            print("⏳ Waiting for backend to start...")
            for i in range(30):  # Wait up to 30 seconds
                if self.check_backend_health():
                    self.backend_ready = True
                    print(f"✅ Backend is running at {self.backend_url}")
                    return True
                time.sleep(1)
                print(f"   Checking... ({i+1}/30)")
            
            print("❌ Backend failed to start within 30 seconds")
            return False
            
        except Exception as e:
            print(f"❌ Failed to start backend: {e}")
            return False
    
    def start_desktop_app(self):
        """Start the Elysian Scribe desktop application"""
        print("\n🖥️ Starting Desktop Application...")
        print("=" * 50)
        
        try:
            # Start desktop app
            desktop_process = subprocess.Popen(
                [sys.executable, "elysian_scribe_backend_integrated.py"],
                cwd=Path.cwd()
            )
            print("✅ Desktop application started!")
            return desktop_process
        except Exception as e:
            print(f"❌ Failed to start desktop app: {e}")
            return None
    
    def open_web_interface(self):
        """Open the web interface in browser"""
        print("\n🌐 Opening Web Interface...")
        try:
            webbrowser.open(self.backend_url)
            print("✅ Web interface opened in browser")
        except Exception as e:
            print(f"❌ Failed to open web interface: {e}")
    
    def show_system_status(self):
        """Show current system status"""
        print("\n📊 System Status")
        print("=" * 50)
        print(f"Backend Server: {'✅ Running' if self.backend_ready else '❌ Not Running'}")
        print(f"Backend URL: {self.backend_url}")
        print(f"Desktop App: {'✅ Available' if Path('elysian_scribe_backend_integrated.py').exists() else '❌ Not Found'}")
        print(f"Web Interface: {'✅ Available' if self.backend_ready else '❌ Not Available'}")
    
    def cleanup(self):
        """Clean up processes on exit"""
        if self.backend_process:
            print("\n🛑 Shutting down backend server...")
            self.backend_process.terminate()
            self.backend_process.wait()
            print("✅ Backend server stopped")
    
    def run(self):
        """Main launcher function"""
        print("🏛️ ELYSIAN FIELDS - Cemetery Management System")
        print("=" * 60)
        print("Complete startup script for backend and desktop application")
        print("=" * 60)
        
        try:
            # Step 1: Install dependencies
            if not self.install_dependencies():
                print("❌ Dependency installation failed. Exiting.")
                return False
            
            # Step 2: Start backend
            if not self.start_backend():
                print("❌ Backend startup failed. Exiting.")
                return False
            
            # Step 3: Show status
            self.show_system_status()
            
            # Step 4: Ask user what to do next
            print("\n🎯 What would you like to do?")
            print("1. Start Desktop Application (Elysian Scribe)")
            print("2. Open Web Interface in Browser")
            print("3. Just keep backend running")
            print("4. Exit")
            
            while True:
                choice = input("\nEnter your choice (1-4): ").strip()
                
                if choice == "1":
                    desktop_process = self.start_desktop_app()
                    if desktop_process:
                        print("\n✅ Desktop application is running!")
                        print("   The backend will continue running in the background.")
                        print("   Press Ctrl+C to stop the backend when you're done.")
                        
                        # Keep backend running
                        try:
                            while True:
                                time.sleep(1)
                        except KeyboardInterrupt:
                            break
                    break
                    
                elif choice == "2":
                    self.open_web_interface()
                    print("\n✅ Web interface opened!")
                    print("   The backend will continue running in the background.")
                    print("   Press Ctrl+C to stop the backend when you're done.")
                    
                    # Keep backend running
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        break
                        
                elif choice == "3":
                    print("\n✅ Backend is running!")
                    print("   You can now use the desktop app or web interface.")
                    print("   Press Ctrl+C to stop the backend when you're done.")
                    
                    # Keep backend running
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        break
                        
                elif choice == "4":
                    print("👋 Goodbye!")
                    break
                    
                else:
                    print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
            
            return True
            
        except KeyboardInterrupt:
            print("\n\n🛑 Shutdown requested by user")
            return True
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    launcher = ElysianFieldsLauncher()
    success = launcher.run()
    
    if success:
        print("\n🎉 Elysian Fields session completed successfully!")
    else:
        print("\n❌ Elysian Fields session encountered errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()
