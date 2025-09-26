"""
Google Maps/Earth Integration for Elysian Fields
Handles GPS coordinate loading, map integration, and blueprint management

Dependencies:
- googlemaps (Google Maps API client)
- folium (for interactive maps)
- requests

Author: Project Elysian Fields Development Team
"""

import os
import json
import requests
from typing import List, Dict, Tuple, Optional
import folium
from folium import plugins
import webbrowser
from pathlib import Path

class GoogleMapsIntegration:
    """Google Maps integration for cemetery management"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        self.base_url = "https://maps.googleapis.com/maps/api"
        # Use absolute path for maps directory
        self.maps_dir = Path(__file__).parent.parent / "maps"
        self.maps_dir.mkdir(exist_ok=True)
        
    def geocode_address(self, address: str) -> Optional[Dict]:
        """Get GPS coordinates for an address"""
        print(f"Looking up GPS coordinates for: {address}")
        
        # Try Google Maps API first if key is available
        if self.api_key:
            try:
                url = f"{self.base_url}/geocode/json"
                params = {
                    'address': address,
                    'key': self.api_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                
                if data['status'] == 'OK' and data['results']:
                    result = data['results'][0]
                    location = result['geometry']['location']
                    print(f"[SUCCESS] Found coordinates via Google Maps API")
                    return {
                        'latitude': location['lat'],
                        'longitude': location['lng'],
                        'formatted_address': result['formatted_address'],
                        'place_id': result['place_id']
                    }
                else:
                    print(f"Google Maps API returned: {data.get('status', 'Unknown error')}")
            except Exception as e:
                print(f"Google Maps API error: {e}")
        
        # Fallback to OpenStreetMap
        print("Trying fallback geocoding service...")
        result = self._fallback_geocode(address)
        if result:
            print(f"[SUCCESS] Found coordinates via fallback service")
            return result
        
        # If all else fails, return None
        print("[ERROR] Could not find GPS coordinates for this address")
        return None
    
    def _fallback_geocode(self, address: str) -> Optional[Dict]:
        """Fallback geocoding using OpenStreetMap Nominatim"""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'ElysianFields/1.0 (Cemetery Management System)'
            }
            
            print(f"Making request to: {url}")
            print(f"Parameters: {params}")
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            print(f"Response status: {response.status_code}")
            print(f"Response content length: {len(response.content)}")
            
            if response.status_code == 200:
                # Check if response has content
                if not response.content:
                    print("Empty response received")
                    return None
                
                try:
                    data = response.json()
                    print(f"Parsed JSON data: {type(data)}, length: {len(data) if isinstance(data, list) else 'not a list'}")
                    
                    if data and len(data) > 0:
                        result = data[0]
                        print(f"Found result: {result.get('display_name', 'No name')}")
                        return {
                            'latitude': float(result['lat']),
                            'longitude': float(result['lon']),
                            'formatted_address': result['display_name'],
                            'place_id': result.get('place_id', '')
                        }
                    else:
                        print(f"No results found for address: {address}")
                except ValueError as json_error:
                    print(f"JSON parsing error: {json_error}")
                    print(f"Response content: {response.text[:200]}...")
                    return None
            else:
                print(f"Geocoding request failed with status: {response.status_code}")
                print(f"Response content: {response.text[:200]}...")
                
        except requests.exceptions.Timeout:
            print("Geocoding request timed out")
        except requests.exceptions.RequestException as e:
            print(f"Network error during geocoding: {e}")
        except Exception as e:
            print(f"Fallback geocoding error: {e}")
            
        return None
    
    def create_interactive_map(self, cemetery_data: Dict, plots: List[Dict]) -> str:
        """Create an interactive map for the cemetery"""
        # Get cemetery center coordinates
        if cemetery_data.get('latitude') and cemetery_data.get('longitude'):
            center_lat = cemetery_data['latitude']
            center_lng = cemetery_data['longitude']
        else:
            # Use first plot coordinates or default
            if plots and plots[0].get('latitude') and plots[0].get('longitude'):
                center_lat = plots[0]['latitude']
                center_lng = plots[0]['longitude']
            else:
                # Default to a central location
                center_lat, center_lng = 40.7128, -74.0060  # New York City
        
        # Create map
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=15,
            tiles='OpenStreetMap'
        )
        
        # Add cemetery marker
        folium.Marker(
            [center_lat, center_lng],
            popup=f"<b>{cemetery_data.get('name', 'Cemetery')}</b><br>{cemetery_data.get('location', '')}",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
        
        # Add plot markers
        for plot in plots:
            if plot.get('latitude') and plot.get('longitude'):
                # Create popup content
                individuals = plot.get('individuals', [])
                popup_content = f"<b>Plot {plot.get('plot_number', 'Unknown')}</b><br>"
                if plot.get('section'):
                    popup_content += f"Section: {plot['section']}<br>"
                if individuals:
                    popup_content += "<br><b>Individuals:</b><br>"
                    for individual in individuals:
                        popup_content += f"• {individual.get('name', 'Unknown')}<br>"
                        if individual.get('born_date'):
                            popup_content += f"  Born: {individual['born_date']}<br>"
                        if individual.get('died_date'):
                            popup_content += f"  Died: {individual['died_date']}<br>"
                
                folium.Marker(
                    [plot['latitude'], plot['longitude']],
                    popup=folium.Popup(popup_content, max_width=300),
                    icon=folium.Icon(color='blue', icon='home')
                ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add fullscreen plugin
        plugins.Fullscreen().add_to(m)
        
        # Save map with absolute path
        map_file = f"cemetery_map_{cemetery_data.get('id', 'unknown')}.html"
        map_path = self.maps_dir / map_file
        m.save(str(map_path))
        
        print(f"[SUCCESS] Map saved to: {map_path}")
        return str(map_path)
    
    def export_to_google_my_maps(self, cemetery_data: Dict, plots: List[Dict]) -> Dict:
        """Export cemetery data in Google My Maps compatible format"""
        kml_data = {
            'name': cemetery_data.get('name', 'Cemetery'),
            'description': cemetery_data.get('description', ''),
            'plots': []
        }
        
        for plot in plots:
            if plot.get('latitude') and plot.get('longitude'):
                plot_data = {
                    'name': f"Plot {plot.get('plot_number', 'Unknown')}",
                    'latitude': plot['latitude'],
                    'longitude': plot['longitude'],
                    'description': f"Section: {plot.get('section', 'N/A')}",
                    'individuals': plot.get('individuals', [])
                }
                kml_data['plots'].append(plot_data)
        
        return kml_data
    
    def load_google_earth_kmz(self, kmz_file_path: str) -> List[Dict]:
        """Load GPS coordinates from Google Earth KMZ file"""
        import zipfile
        import xml.etree.ElementTree as ET
        
        plots = []
        
        try:
            with zipfile.ZipFile(kmz_file_path, 'r') as kmz:
                # Find KML files
                kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]
                
                for kml_file in kml_files:
                    kml_content = kmz.read(kml_file)
                    plots.extend(self._parse_kml_content(kml_content))
                    
        except Exception as e:
            print(f"Error loading KMZ file: {e}")
            
        return plots
    
    def _parse_kml_content(self, kml_content: bytes) -> List[Dict]:
        """Parse KML content to extract plot data"""
        import xml.etree.ElementTree as ET
        
        plots = []
        
        try:
            root = ET.fromstring(kml_content)
            
            # Find all Placemark elements
            for placemark in root.findall('.//{http://www.opengis.net/kml/2.2}Placemark'):
                name_elem = placemark.find('.//{http://www.opengis.net/kml/2.2}name')
                coord_elem = placemark.find('.//{http://www.opengis.net/kml/2.2}coordinates')
                desc_elem = placemark.find('.//{http://www.opengis.net/kml/2.2}description')
                
                if name_elem is not None and coord_elem is not None:
                    name = name_elem.text or 'Unknown'
                    coords = coord_elem.text.strip().split(',')
                    
                    if len(coords) >= 2:
                        plot_data = {
                            'plot_number': name,
                            'latitude': float(coords[1]),
                            'longitude': float(coords[0]),
                            'description': desc_elem.text if desc_elem is not None else ''
                        }
                        plots.append(plot_data)
                        
        except Exception as e:
            print(f"Error parsing KML: {e}")
            
        return plots
    
    def create_blueprint_overlay(self, cemetery_data: Dict, blueprint_image_path: str, 
                                reference_points: List[Dict]) -> str:
        """Create a map with blueprint overlay"""
        if not reference_points:
            print("Reference points required for blueprint overlay")
            return None
        
        # Create base map
        center_lat = sum(point['latitude'] for point in reference_points) / len(reference_points)
        center_lng = sum(point['longitude'] for point in reference_points) / len(reference_points)
        
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=18,
            tiles='OpenStreetMap'
        )
        
        # Add blueprint overlay
        if os.path.exists(blueprint_image_path):
            # Calculate bounds for the blueprint
            lats = [point['latitude'] for point in reference_points]
            lngs = [point['longitude'] for point in reference_points]
            
            bounds = [
                [min(lats), min(lngs)],
                [max(lats), max(lngs)]
            ]
            
            # Add image overlay
            folium.raster_layers.ImageOverlay(
                image=blueprint_image_path,
                bounds=bounds,
                opacity=0.7,
                interactive=True,
                cross_origin=False
            ).add_to(m)
        
        # Add reference points
        for i, point in enumerate(reference_points):
            folium.Marker(
                [point['latitude'], point['longitude']],
                popup=f"Reference Point {i+1}",
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)
        
        # Save map
        map_file = f"blueprint_overlay_{cemetery_data.get('id', 'unknown')}.html"
        m.save(map_file)
        
        return map_file

class CemeteryMapManager:
    """Manages cemetery maps and GPS integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.google_maps = GoogleMapsIntegration(api_key)
        self.maps_dir = Path("maps")
        self.maps_dir.mkdir(exist_ok=True)
    
    def setup_cemetery_location(self, cemetery_name: str, address: str) -> Optional[Dict]:
        """Set up cemetery location using GPS coordinates"""
        print(f"Setting up location for {cemetery_name}...")
        
        # Geocode the address
        location_data = self.google_maps.geocode_address(address)
        
        if location_data:
            print(f"[SUCCESS] Found location: {location_data['formatted_address']}")
            print(f"   Coordinates: {location_data['latitude']}, {location_data['longitude']}")
            return location_data
        else:
            print("[ERROR] Could not find GPS coordinates for the address")
            return None
    
    def import_google_earth_data(self, kmz_file_path: str) -> List[Dict]:
        """Import plot data from Google Earth KMZ file"""
        print(f"Importing data from {kmz_file_path}...")
        
        plots = self.google_maps.load_google_earth_kmz(kmz_file_path)
        
        if plots:
            print(f"[SUCCESS] Imported {len(plots)} plots from Google Earth")
            for plot in plots[:5]:  # Show first 5 plots
                print(f"   Plot {plot['plot_number']}: {plot['latitude']}, {plot['longitude']}")
            if len(plots) > 5:
                print(f"   ... and {len(plots) - 5} more plots")
        else:
            print("[ERROR] No plots found in the KMZ file")
            
        return plots
    
    def create_cemetery_map(self, cemetery_data: Dict, plots: List[Dict]) -> str:
        """Create an interactive cemetery map"""
        print(f"Creating interactive map for {cemetery_data.get('name', 'Cemetery')}...")
        
        map_file = self.google_maps.create_interactive_map(cemetery_data, plots)
        map_path = self.maps_dir / map_file
        
        print(f"[SUCCESS] Map created: {map_path}")
        print(f"   Open in browser: file://{map_path.absolute()}")
        
        return str(map_path)
    
    def setup_blueprint_overlay(self, cemetery_data: Dict, blueprint_path: str, 
                               reference_points: List[Dict]) -> str:
        """Set up blueprint overlay on map"""
        print(f"Setting up blueprint overlay for {cemetery_data.get('name', 'Cemetery')}...")
        
        if not reference_points:
            print("[ERROR] Reference points required for blueprint overlay")
            print("   Please provide at least 2 GPS coordinates that correspond to points on the blueprint")
            return None
        
        map_file = self.google_maps.create_blueprint_overlay(
            cemetery_data, blueprint_path, reference_points
        )
        
        if map_file:
            map_path = self.maps_dir / map_file
            print(f"[SUCCESS] Blueprint overlay created: {map_path}")
            print(f"   Open in browser: file://{map_path.absolute()}")
            return str(map_path)
        
        return None

# Example usage
if __name__ == "__main__":
    # Initialize map manager
    map_manager = CemeteryMapManager()
    
    # Example: Set up cemetery location
    cemetery_data = {
        'name': 'Oakwood Cemetery',
        'location': '123 Cemetery Road, Anytown, USA'
    }
    
    location = map_manager.setup_cemetery_location(
        cemetery_data['name'], 
        cemetery_data['location']
    )
    
    if location:
        cemetery_data.update(location)
        
        # Example plots
        plots = [
            {
                'plot_number': 'A-001',
                'latitude': location['latitude'] + 0.001,
                'longitude': location['longitude'] + 0.001,
                'individuals': [
                    {'name': 'John Smith', 'born_date': '1920-01-15', 'died_date': '1995-03-22'}
                ]
            }
        ]
        
        # Create interactive map
        map_path = map_manager.create_cemetery_map(cemetery_data, plots)
        
        print(f"\n[SUCCESS] Cemetery setup complete!")
        print(f"   Interactive map: {map_path}")
        print(f"   GPS coordinates: {location['latitude']}, {location['longitude']}")
