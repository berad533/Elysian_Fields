"""
Elysian Fields Mobile Client
A Python client for mobile devices (Android) to interact with the backend API

Dependencies:
- requests
- pillow (PIL)
- pytesseract

Author: Project Elysian Fields Development Team
"""

import requests
import json
import os
from pathlib import Path
from PIL import Image
import pytesseract
from datetime import datetime

class ElysianFieldsClient:
    """Client for interacting with Elysian Fields backend API"""
    
    def __init__(self, base_url="http://localhost:5000/api"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def health_check(self):
        """Check if the backend is running"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False
    
    def create_cemetery(self, name, location="", description=""):
        """Create a new cemetery"""
        data = {
            "name": name,
            "location": location,
            "description": description
        }
        response = self.session.post(f"{self.base_url}/cemeteries", json=data)
        return response.json() if response.status_code == 201 else None
    
    def get_cemeteries(self):
        """Get all cemeteries"""
        response = self.session.get(f"{self.base_url}/cemeteries")
        return response.json() if response.status_code == 200 else []
    
    def create_plot(self, cemetery_id, plot_number, section="", row="", latitude=None, longitude=None):
        """Create a new plot"""
        data = {
            "plot_number": plot_number,
            "section": section,
            "row": row,
            "latitude": latitude,
            "longitude": longitude
        }
        response = self.session.post(f"{self.base_url}/cemeteries/{cemetery_id}/plots", json=data)
        return response.json() if response.status_code == 201 else None
    
    def add_individual(self, plot_id, name, born_date=None, died_date=None, epitaph="", relationship=""):
        """Add an individual to a plot"""
        data = {
            "name": name,
            "born_date": born_date,
            "died_date": died_date,
            "epitaph": epitaph,
            "relationship": relationship
        }
        response = self.session.post(f"{self.base_url}/plots/{plot_id}/individuals", json=data)
        return response.json() if response.status_code == 201 else None
    
    def upload_photo(self, plot_id, image_path, photo_type="headstone"):
        """Upload a photo for a plot"""
        if not os.path.exists(image_path):
            return None
        
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = {'photo_type': photo_type}
            response = self.session.post(f"{self.base_url}/plots/{plot_id}/photos", files=files, data=data)
        
        return response.json() if response.status_code == 201 else None
    
    def upload_360_photo(self, plot_id, image_path):
        """Upload a 360-degree photo"""
        return self.upload_photo(plot_id, image_path, "360")
    
    def upload_blueprint(self, cemetery_id, image_path, description="", scale=1.0):
        """Upload a blueprint for a cemetery"""
        if not os.path.exists(image_path):
            return None
        
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = {
                'description': description,
                'scale': str(scale)
            }
            response = self.session.post(f"{self.base_url}/cemeteries/{cemetery_id}/blueprints", files=files, data=data)
        
        return response.json() if response.status_code == 201 else None
    
    def import_kmz(self, cemetery_id, kmz_path):
        """Import KMZ/KML file to create plots with coordinates"""
        if not os.path.exists(kmz_path):
            return None
        
        with open(kmz_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(f"{self.base_url}/cemeteries/{cemetery_id}/import-kmz", files=files)
        
        return response.json() if response.status_code == 201 else None
    
    def search(self, query):
        """Search across cemeteries, plots, and individuals"""
        response = self.session.get(f"{self.base_url}/search", params={'q': query})
        return response.json() if response.status_code == 200 else {}
    
    def get_plots(self, cemetery_id):
        """Get all plots for a cemetery"""
        response = self.session.get(f"{self.base_url}/cemeteries/{cemetery_id}/plots")
        return response.json() if response.status_code == 200 else []
    
    def export_google_maps(self, cemetery_id):
        """Export cemetery data for Google My Maps"""
        response = self.session.get(f"{self.base_url}/export/google-maps/{cemetery_id}")
        return response.json() if response.status_code == 200 else {}

class MobileWorkflow:
    """Workflow helper for mobile cemetery data collection"""
    
    def __init__(self, client):
        self.client = client
    
    def setup_cemetery(self, cemetery_name, location="", description=""):
        """Set up a new cemetery"""
        # Check if cemetery already exists
        cemeteries = self.client.get_cemeteries()
        existing = next((c for c in cemeteries if c['name'] == cemetery_name), None)
        
        if existing:
            print(f"Cemetery '{cemetery_name}' already exists")
            return existing['id']
        
        # Create new cemetery
        result = self.client.create_cemetery(cemetery_name, location, description)
        if result:
            print(f"Created cemetery '{cemetery_name}' with ID {result['id']}")
            return result['id']
        else:
            print(f"Failed to create cemetery '{cemetery_name}'")
            return None
    
    def process_headstone_photo(self, cemetery_id, plot_number, image_path, individuals_data):
        """Process a headstone photo and create plot with individuals"""
        # Create plot
        plot = self.client.create_plot(cemetery_id, plot_number)
        if not plot:
            print(f"Failed to create plot {plot_number}")
            return False
        
        plot_id = plot['id']
        
        # Upload photo
        photo_result = self.client.upload_photo(plot_id, image_path, "headstone")
        if photo_result:
            print(f"Uploaded headstone photo for plot {plot_number}")
        
        # Add individuals
        for individual in individuals_data:
            result = self.client.add_individual(
                plot_id,
                individual['name'],
                individual.get('born_date'),
                individual.get('died_date'),
                individual.get('epitaph', ''),
                individual.get('relationship', '')
            )
            if result:
                print(f"Added individual: {individual['name']}")
        
        return True
    
    def batch_upload_photos(self, cemetery_id, photos_directory, photo_type="headstone"):
        """Batch upload photos from a directory"""
        photos_dir = Path(photos_directory)
        if not photos_dir.exists():
            print(f"Directory {photos_directory} does not exist")
            return
        
        uploaded_count = 0
        for photo_file in photos_dir.glob("*.jpg"):
            # Extract plot number from filename (assuming format: plot_123.jpg)
            plot_number = photo_file.stem.replace("plot_", "")
            
            # Create plot
            plot = self.client.create_plot(cemetery_id, plot_number)
            if plot:
                # Upload photo
                result = self.client.upload_photo(plot['id'], str(photo_file), photo_type)
                if result:
                    uploaded_count += 1
                    print(f"Uploaded {photo_file.name}")
        
        print(f"Successfully uploaded {uploaded_count} photos")

# Example usage
if __name__ == "__main__":
    # Initialize client
    client = ElysianFieldsClient("http://localhost:5000/api")
    
    # Check if backend is running
    if not client.health_check():
        print("Backend is not running. Please start the Flask server first.")
        exit(1)
    
    # Example workflow
    workflow = MobileWorkflow(client)
    
    # Set up cemetery
    cemetery_id = workflow.setup_cemetery(
        "Oakwood Cemetery",
        "123 Cemetery Road, Anytown, USA",
        "Historic cemetery established in 1850"
    )
    
    if cemetery_id:
        # Process a headstone photo
        individuals_data = [
            {
                "name": "John Smith",
                "born_date": "1920-01-15",
                "died_date": "1995-03-22",
                "epitaph": "Beloved husband and father",
                "relationship": "primary"
            },
            {
                "name": "Mary Smith",
                "born_date": "1925-06-10",
                "died_date": "2001-12-05",
                "epitaph": "Beloved wife and mother",
                "relationship": "spouse"
            }
        ]
        
        # Note: Replace with actual image path
        # workflow.process_headstone_photo(cemetery_id, "A-123", "path/to/headstone.jpg", individuals_data)
        
        print("Example workflow completed. Replace with actual image paths to test.")
