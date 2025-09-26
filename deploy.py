"""
Elysian Fields Deployment Script
Sets up the complete cemetery management system

Usage:
    python deploy.py

Author: Project Elysian Fields Development Team
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"Running: {description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("✗ Python 3.8 or higher is required")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def check_tesseract():
    """Check if Tesseract is installed"""
    try:
        result = subprocess.run("tesseract --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Tesseract OCR is installed")
            return True
    except:
        pass
    
    print("✗ Tesseract OCR is not installed")
    print("Please install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
    return False

def install_dependencies():
    """Install Python dependencies"""
    print("\n=== Installing Dependencies ===")
    
    # Backend dependencies
    if not run_command("pip install -r backend/requirements.txt", "Installing backend dependencies"):
        return False
    
    # Additional dependencies for desktop app
    desktop_deps = [
        "customtkinter",
        "opencv-python",
        "numpy",
        "pandas",
        "requests"
    ]
    
    for dep in desktop_deps:
        if not run_command(f"pip install {dep}", f"Installing {dep}"):
            return False
    
    return True

def setup_directories():
    """Create necessary directories"""
    print("\n=== Setting Up Directories ===")
    
    directories = [
        "backend/uploads",
        "backend/uploads/cemeteries",
        "backend/uploads/blueprints",
        "backend/uploads/headstones",
        "backend/uploads/360_photos",
        "backend/uploads/temp"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {directory}")
    
    return True

def setup_environment():
    """Set up environment configuration"""
    print("\n=== Setting Up Environment ===")
    
    env_file = Path("backend/.env")
    env_example = Path("backend/env_example.txt")
    
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        print("✓ Created .env file from template")
        print("⚠ Please edit backend/.env with your configuration")
    elif env_file.exists():
        print("✓ .env file already exists")
    else:
        print("✗ Could not find environment template")
        return False
    
    return True

def test_backend():
    """Test if backend can start"""
    print("\n=== Testing Backend ===")
    
    try:
        # Try to import the backend
        sys.path.insert(0, str(Path("backend")))
        from app import app
        
        with app.app_context():
            from app import db
            db.create_all()
        
        print("✓ Backend imports successfully")
        print("✓ Database tables created")
        return True
    except Exception as e:
        print(f"✗ Backend test failed: {e}")
        return False

def main():
    """Main deployment function"""
    print("=== Elysian Fields Deployment ===")
    print("Setting up the complete cemetery management system...\n")
    
    # Check prerequisites
    if not check_python_version():
        sys.exit(1)
    
    if not check_tesseract():
        print("\n⚠ Tesseract is required for OCR functionality")
        print("You can continue without it, but OCR features will not work")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n✗ Failed to install dependencies")
        sys.exit(1)
    
    # Setup directories
    if not setup_directories():
        print("\n✗ Failed to setup directories")
        sys.exit(1)
    
    # Setup environment
    if not setup_environment():
        print("\n✗ Failed to setup environment")
        sys.exit(1)
    
    # Test backend
    if not test_backend():
        print("\n✗ Backend test failed")
        sys.exit(1)
    
    print("\n=== Deployment Complete ===")
    print("✓ All components installed successfully")
    print("\nNext steps:")
    print("1. Edit backend/.env with your configuration")
    print("2. Start the backend server: python start_backend.py")
    print("3. Run the desktop app: python elysian_scribe_backend_integrated.py")
    print("\nFor more information, see README.md")

if __name__ == "__main__":
    main()
