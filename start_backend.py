"""
Elysian Fields Backend Startup Script
Starts the Flask backend server for the cemetery management system

Usage:
    python start_backend.py

Author: Project Elysian Fields Development Team
"""

import os
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Change to backend directory
os.chdir(backend_dir)

# Import and run the Flask app
from app import app

if __name__ == "__main__":
    print("Starting Elysian Fields Backend Server...")
    print("Backend will be available at: http://localhost:5000")
    print("API documentation available at: http://localhost:5000/api/health")
    print("Press Ctrl+C to stop the server")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nShutting down backend server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)
