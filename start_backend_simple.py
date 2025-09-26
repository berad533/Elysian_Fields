"""
Elysian Fields Backend Startup Script (Simple Version)
Starts the Flask backend server for the cemetery management system

Usage:
    python start_backend_simple.py

Author: Project Elysian Fields Development Team
"""

import os
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Import and run the Flask app
from app import app

if __name__ == "__main__":
    print("Starting Elysian Fields Backend Server...")
    print("Backend will be available at: http://localhost:5000")
    print("API documentation available at: http://localhost:5000/api/health")
    print("Press Ctrl+C to stop the server")
    
    try:
        # Change to backend directory for file operations
        original_dir = os.getcwd()
        os.chdir(backend_dir)
        
        app.run(debug=True, host='0.0.0.0', port=5000)
        
    except KeyboardInterrupt:
        print("\nShutting down backend server...")
        os.chdir(original_dir)
    except Exception as e:
        print(f"Error starting server: {e}")
        os.chdir(original_dir)
        sys.exit(1)
