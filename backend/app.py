"""
Elysian Fields Backend Server
A Flask-based backend for cemetery management with OCR, file upload, and Google Maps integration

Dependencies:
- flask
- flask-cors
- sqlalchemy
- pillow (PIL)
- pytesseract
- opencv-python
- numpy
- pandas
- python-dotenv

Author: Project Elysian Fields Development Team
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import cv2
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google_maps_integration import CemeteryMapManager

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///elysian_fields.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Initialize extensions
db = SQLAlchemy(app)

# Initialize Google Maps integration
map_manager = CemeteryMapManager()

# Tesseract configuration
pytesseract.pytesseract.tesseract_cmd = os.getenv('TESSERACT_PATH', r'C:\Program Files\Tesseract-OCR\tesseract.exe')

# Create upload directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('uploads/cemeteries', exist_ok=True)
os.makedirs('uploads/blueprints', exist_ok=True)
os.makedirs('uploads/headstones', exist_ok=True)
os.makedirs('uploads/360_photos', exist_ok=True)

# Database Models
class Cemetery(db.Model):
    """Cemetery information"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    location = db.Column(db.String(300))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    plots = db.relationship('Plot', backref='cemetery', lazy=True, cascade='all, delete-orphan')
    blueprints = db.relationship('Blueprint', backref='cemetery', lazy=True, cascade='all, delete-orphan')

class Plot(db.Model):
    """Individual plot/grave information"""
    id = db.Column(db.Integer, primary_key=True)
    cemetery_id = db.Column(db.Integer, db.ForeignKey('cemetery.id'), nullable=False)
    plot_number = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(50))
    row = db.Column(db.String(50))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default='active')  # active, reserved, sold
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    individuals = db.relationship('Individual', backref='plot', lazy=True, cascade='all, delete-orphan')
    photos = db.relationship('Photo', backref='plot', lazy=True, cascade='all, delete-orphan')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('cemetery_id', 'plot_number', name='unique_plot_per_cemetery'),)

class Individual(db.Model):
    """Individual person information"""
    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey('plot.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    born_date = db.Column(db.Date)
    died_date = db.Column(db.Date)
    epitaph = db.Column(db.Text)
    relationship = db.Column(db.String(100))  # spouse, child, parent, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Photo(db.Model):
    """Photo metadata"""
    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey('plot.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    photo_type = db.Column(db.String(50))  # headstone, 360, blueprint, etc.
    ocr_text = db.Column(db.Text)
    ocr_confidence = db.Column(db.Float)
    file_size = db.Column(db.Integer)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Blueprint(db.Model):
    """Cemetery blueprint/map information"""
    id = db.Column(db.Integer, primary_key=True)
    cemetery_id = db.Column(db.Integer, db.ForeignKey('cemetery.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    scale = db.Column(db.Float)  # Scale factor for the blueprint
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Utility Functions
def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def process_ocr(image_path):
    """Process OCR on an image"""
    try:
        image = Image.open(image_path)
        ocr_text = pytesseract.image_to_string(image, lang='eng')
        return ocr_text.strip(), 0.8  # Placeholder confidence
    except Exception as e:
        print(f"OCR Error: {str(e)}")
        return "", 0.0

def extract_kmz_data(kmz_path):
    """Extract data from KMZ file"""
    try:
        with zipfile.ZipFile(kmz_path, 'r') as kmz:
            # Look for KML files in the KMZ
            kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]
            if kml_files:
                kml_content = kmz.read(kml_files[0])
                return parse_kml_data(kml_content)
    except Exception as e:
        print(f"KMZ extraction error: {str(e)}")
    return []

def parse_kml_data(kml_content):
    """Parse KML data to extract coordinates and names"""
    try:
        root = ET.fromstring(kml_content)
        places = []
        
        # Find all Placemark elements
        for placemark in root.findall('.//{http://www.opengis.net/kml/2.2}Placemark'):
            name_elem = placemark.find('.//{http://www.opengis.net/kml/2.2}name')
            coord_elem = placemark.find('.//{http://www.opengis.net/kml/2.2}coordinates')
            
            if name_elem is not None and coord_elem is not None:
                name = name_elem.text
                coords = coord_elem.text.strip().split(',')
                if len(coords) >= 2:
                    places.append({
                        'name': name,
                        'longitude': float(coords[0]),
                        'latitude': float(coords[1])
                    })
        return places
    except Exception as e:
        print(f"KML parsing error: {str(e)}")
    return []

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/api/cemeteries', methods=['GET'])
def get_cemeteries():
    """Get all cemeteries"""
    cemeteries = Cemetery.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'location': c.location,
        'description': c.description,
        'plot_count': len(c.plots),
        'created_at': c.created_at.isoformat()
    } for c in cemeteries])

@app.route('/api/cemeteries', methods=['POST'])
def create_cemetery():
    """Create a new cemetery"""
    data = request.get_json()
    
    if not data or not data.get('name'):
        return jsonify({'error': 'Cemetery name is required'}), 400
    
    # Check if cemetery already exists
    existing = Cemetery.query.filter_by(name=data['name']).first()
    if existing:
        return jsonify({'error': 'Cemetery with this name already exists'}), 400
    
    cemetery = Cemetery(
        name=data['name'],
        location=data.get('location', ''),
        description=data.get('description', '')
    )
    
    db.session.add(cemetery)
    db.session.commit()
    
    # Create cemetery directory
    cemetery_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'cemeteries', secure_filename(data['name']))
    os.makedirs(cemetery_dir, exist_ok=True)
    os.makedirs(os.path.join(cemetery_dir, 'blueprints'), exist_ok=True)
    os.makedirs(os.path.join(cemetery_dir, 'headstones'), exist_ok=True)
    os.makedirs(os.path.join(cemetery_dir, '360_photos'), exist_ok=True)
    
    return jsonify({
        'id': cemetery.id,
        'name': cemetery.name,
        'location': cemetery.location,
        'description': cemetery.description,
        'created_at': cemetery.created_at.isoformat()
    }), 201

@app.route('/api/cemeteries/<int:cemetery_id>', methods=['DELETE'])
def delete_cemetery(cemetery_id):
    """Delete a cemetery and all its associated data"""
    cemetery = Cemetery.query.get_or_404(cemetery_id)
    
    # Delete the cemetery directory if it exists
    cemetery_dir = os.path.join('cemeteries', cemetery.name)
    if os.path.exists(cemetery_dir):
        import shutil
        shutil.rmtree(cemetery_dir)
    
    # Delete from database (cascade will handle related records)
    db.session.delete(cemetery)
    db.session.commit()
    
    return jsonify({'message': f'Cemetery {cemetery.name} deleted successfully'}), 200

@app.route('/api/cemeteries/<int:cemetery_id>/plots', methods=['GET'])
def get_plots(cemetery_id):
    """Get all plots for a cemetery"""
    cemetery = Cemetery.query.get_or_404(cemetery_id)
    plots = Plot.query.filter_by(cemetery_id=cemetery_id).all()
    
    return jsonify([{
        'id': p.id,
        'plot_number': p.plot_number,
        'section': p.section,
        'row': p.row,
        'latitude': p.latitude,
        'longitude': p.longitude,
        'status': p.status,
        'individual_count': len(p.individuals),
        'photo_count': len(p.photos)
    } for p in plots])

@app.route('/api/cemeteries/<int:cemetery_id>/plots', methods=['POST'])
def create_plot(cemetery_id):
    """Create a new plot"""
    cemetery = Cemetery.query.get_or_404(cemetery_id)
    data = request.get_json()
    
    if not data or not data.get('plot_number'):
        return jsonify({'error': 'Plot number is required'}), 400
    
    # Check if plot already exists in this cemetery
    existing = Plot.query.filter_by(cemetery_id=cemetery_id, plot_number=data['plot_number']).first()
    if existing:
        return jsonify({'error': 'Plot with this number already exists in this cemetery'}), 400
    
    plot = Plot(
        cemetery_id=cemetery_id,
        plot_number=data['plot_number'],
        section=data.get('section', ''),
        row=data.get('row', ''),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        status=data.get('status', 'active')
    )
    
    db.session.add(plot)
    db.session.commit()
    
    return jsonify({
        'id': plot.id,
        'plot_number': plot.plot_number,
        'section': plot.section,
        'row': plot.row,
        'latitude': plot.latitude,
        'longitude': plot.longitude,
        'status': plot.status
    }), 201

@app.route('/api/plots/<int:plot_id>/individuals', methods=['POST'])
def add_individual(plot_id):
    """Add an individual to a plot"""
    plot = Plot.query.get_or_404(plot_id)
    data = request.get_json()
    
    if not data or not data.get('name'):
        return jsonify({'error': 'Individual name is required'}), 400
    
    individual = Individual(
        plot_id=plot_id,
        name=data['name'],
        born_date=datetime.strptime(data['born_date'], '%Y-%m-%d').date() if data.get('born_date') else None,
        died_date=datetime.strptime(data['died_date'], '%Y-%m-%d').date() if data.get('died_date') else None,
        epitaph=data.get('epitaph', ''),
        relationship=data.get('relationship', '')
    )
    
    db.session.add(individual)
    db.session.commit()
    
    return jsonify({
        'id': individual.id,
        'name': individual.name,
        'born_date': individual.born_date.isoformat() if individual.born_date else None,
        'died_date': individual.died_date.isoformat() if individual.died_date else None,
        'epitaph': individual.epitaph,
        'relationship': individual.relationship
    }), 201

@app.route('/api/plots/<int:plot_id>/photos', methods=['POST'])
def upload_photo(plot_id):
    """Upload a photo for a plot"""
    plot = Plot.query.get_or_404(plot_id)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Get photo type from form data
    photo_type = request.form.get('photo_type', 'headstone')
    
    if file and allowed_file(file.filename, {'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'tif'}):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        # Save to cemetery-specific directory
        cemetery_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'cemeteries', secure_filename(plot.cemetery.name))
        photo_dir = os.path.join(cemetery_dir, photo_type + 's')
        os.makedirs(photo_dir, exist_ok=True)
        
        file_path = os.path.join(photo_dir, filename)
        file.save(file_path)
        
        # Process OCR if it's a headstone photo
        ocr_text = ""
        ocr_confidence = 0.0
        if photo_type == 'headstone':
            ocr_text, ocr_confidence = process_ocr(file_path)
        
        # Get image dimensions
        try:
            with Image.open(file_path) as img:
                width, height = img.size
        except:
            width, height = 0, 0
        
        # Save photo metadata to database
        photo = Photo(
            plot_id=plot_id,
            filename=filename,
            file_path=file_path,
            photo_type=photo_type,
            ocr_text=ocr_text,
            ocr_confidence=ocr_confidence,
            file_size=os.path.getsize(file_path),
            width=width,
            height=height
        )
        
        db.session.add(photo)
        db.session.commit()
        
        return jsonify({
            'id': photo.id,
            'filename': photo.filename,
            'photo_type': photo.photo_type,
            'ocr_text': photo.ocr_text,
            'ocr_confidence': photo.ocr_confidence,
            'file_size': photo.file_size,
            'width': photo.width,
            'height': photo.height,
            'created_at': photo.created_at.isoformat()
        }), 201
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/cemeteries/<int:cemetery_id>/blueprints', methods=['POST'])
def upload_blueprint(cemetery_id):
    """Upload a blueprint for a cemetery"""
    cemetery = Cemetery.query.get_or_404(cemetery_id)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename, {'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'tif', 'pdf'}):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        # Save to blueprints directory
        blueprint_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'cemeteries', secure_filename(cemetery.name), 'blueprints')
        os.makedirs(blueprint_dir, exist_ok=True)
        
        file_path = os.path.join(blueprint_dir, filename)
        file.save(file_path)
        
        # Save blueprint metadata
        blueprint = Blueprint(
            cemetery_id=cemetery_id,
            filename=filename,
            file_path=file_path,
            description=request.form.get('description', ''),
            scale=float(request.form.get('scale', 1.0))
        )
        
        db.session.add(blueprint)
        db.session.commit()
        
        return jsonify({
            'id': blueprint.id,
            'filename': blueprint.filename,
            'description': blueprint.description,
            'scale': blueprint.scale,
            'created_at': blueprint.created_at.isoformat()
        }), 201
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/cemeteries/<int:cemetery_id>/import-kmz', methods=['POST'])
def import_kmz(cemetery_id):
    """Import KMZ/KML file to create plots with coordinates"""
    cemetery = Cemetery.query.get_or_404(cemetery_id)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename, {'kmz', 'kml'}):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        # Save file temporarily
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)
        
        # Extract data
        places = []
        if filename.endswith('.kmz'):
            places = extract_kmz_data(temp_path)
        elif filename.endswith('.kml'):
            with open(temp_path, 'rb') as f:
                places = parse_kml_data(f.read())
        
        # Create plots from extracted data
        created_plots = []
        for place in places:
            plot = Plot(
                cemetery_id=cemetery_id,
                plot_number=place['name'],
                latitude=place['latitude'],
                longitude=place['longitude']
            )
            db.session.add(plot)
            created_plots.append({
                'plot_number': place['name'],
                'latitude': place['latitude'],
                'longitude': place['longitude']
            })
        
        db.session.commit()
        
        # Clean up temp file
        os.remove(temp_path)
        
        return jsonify({
            'message': f'Successfully imported {len(created_plots)} plots',
            'plots': created_plots
        }), 201
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/search', methods=['GET'])
def search():
    """Search across cemeteries, plots, and individuals"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Search query is required'}), 400
    
    # Search individuals
    individuals = Individual.query.filter(
        Individual.name.ilike(f'%{query}%')
    ).all()
    
    # Search plots
    plots = Plot.query.filter(
        Plot.plot_number.ilike(f'%{query}%')
    ).all()
    
    # Search cemeteries
    cemeteries = Cemetery.query.filter(
        Cemetery.name.ilike(f'%{query}%')
    ).all()
    
    return jsonify({
        'individuals': [{
            'id': i.id,
            'name': i.name,
            'born_date': i.born_date.isoformat() if i.born_date else None,
            'died_date': i.died_date.isoformat() if i.died_date else None,
            'plot_number': i.plot.plot_number,
            'cemetery_name': i.plot.cemetery.name
        } for i in individuals],
        'plots': [{
            'id': p.id,
            'plot_number': p.plot_number,
            'section': p.section,
            'row': p.row,
            'cemetery_name': p.cemetery.name,
            'individual_count': len(p.individuals)
        } for p in plots],
        'cemeteries': [{
            'id': c.id,
            'name': c.name,
            'location': c.location,
            'plot_count': len(c.plots)
        } for c in cemeteries]
    })

@app.route('/api/cemeteries/<int:cemetery_id>/setup-location', methods=['POST'])
def setup_cemetery_location(cemetery_id):
    """Set up cemetery location using GPS coordinates"""
    try:
        cemetery = Cemetery.query.get_or_404(cemetery_id)
        data = request.get_json()
        
        if not data or not data.get('address'):
            return jsonify({'error': 'Address is required'}), 400
        
        address = data['address'].strip()
        if not address:
            return jsonify({'error': 'Address cannot be empty'}), 400
        
        print(f"Setting up location for cemetery {cemetery.name} with address: {address}")
        
        # Get GPS coordinates for the address
        location_data = map_manager.setup_cemetery_location(cemetery.name, address)
        
        if location_data:
            # Update cemetery with GPS coordinates
            cemetery.latitude = location_data['latitude']
            cemetery.longitude = location_data['longitude']
            db.session.commit()
            
            return jsonify({
                'success': True,
                'location': location_data,
                'message': f'Cemetery location set to {location_data["formatted_address"]}'
            })
        else:
            return jsonify({
                'error': 'Could not find GPS coordinates for the address. Please try a more specific address or use manual coordinates.',
                'suggestion': 'Try including city and state, e.g., "Cemetery Name, City, State"'
            }), 400
            
    except Exception as e:
        print(f"Error in setup_cemetery_location: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/cemeteries/<int:cemetery_id>/import-google-earth', methods=['POST'])
def import_google_earth_data(cemetery_id):
    """Import plot data from Google Earth KMZ file"""
    cemetery = Cemetery.query.get_or_404(cemetery_id)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename, {'kmz', 'kml'}):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        # Save file temporarily
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)
        
        # Import data from Google Earth
        plots_data = map_manager.import_google_earth_data(temp_path)
        
        # Create plots in database
        created_plots = []
        for plot_data in plots_data:
            plot = Plot(
                cemetery_id=cemetery_id,
                plot_number=plot_data['plot_number'],
                latitude=plot_data['latitude'],
                longitude=plot_data['longitude'],
                section=plot_data.get('section', ''),
                row=plot_data.get('row', '')
            )
            db.session.add(plot)
            created_plots.append({
                'plot_number': plot_data['plot_number'],
                'latitude': plot_data['latitude'],
                'longitude': plot_data['longitude']
            })
        
        db.session.commit()
        
        # Clean up temp file
        os.remove(temp_path)
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {len(created_plots)} plots from Google Earth',
            'plots': created_plots
        })
    
    return jsonify({'error': 'Invalid file type. Please upload a KMZ or KML file.'}), 400

@app.route('/api/cemeteries/<int:cemetery_id>/create-map', methods=['POST'])
def create_cemetery_map(cemetery_id):
    """Create an interactive map for the cemetery"""
    try:
        cemetery = Cemetery.query.get_or_404(cemetery_id)
        plots = Plot.query.filter_by(cemetery_id=cemetery_id).all()
        
        # Check if cemetery has GPS coordinates
        if not cemetery.latitude or not cemetery.longitude:
            return jsonify({
                'error': 'Cemetery must have GPS coordinates to create a map. Please set up the location first.'
            }), 400
        
        # Prepare cemetery data
        cemetery_data = {
            'id': cemetery.id,
            'name': cemetery.name,
            'location': cemetery.location,
            'latitude': cemetery.latitude,
            'longitude': cemetery.longitude
        }
        
        # Prepare plots data
        plots_data = []
        for plot in plots:
            plot_data = {
                'plot_number': plot.plot_number,
                'latitude': plot.latitude,
                'longitude': plot.longitude,
                'section': plot.section,
                'individuals': [{
                    'name': i.name,
                    'born_date': i.born_date.isoformat() if i.born_date else None,
                    'died_date': i.died_date.isoformat() if i.died_date else None,
                    'epitaph': i.epitaph
                } for i in plot.individuals]
            }
            plots_data.append(plot_data)
        
        # Create interactive map
        map_path = map_manager.create_cemetery_map(cemetery_data, plots_data)
        
        if map_path:
            return jsonify({
                'success': True,
                'map_path': map_path,
                'message': f'Interactive map created for {cemetery.name}'
            })
        else:
            return jsonify({
                'error': 'Failed to create map. Please check the logs for details.'
            }), 500
            
    except Exception as e:
        print(f"Error creating map: {e}")
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/cemeteries/<int:cemetery_id>/blueprint-overlay', methods=['POST'])
def create_blueprint_overlay(cemetery_id):
    """Create blueprint overlay on map"""
    cemetery = Cemetery.query.get_or_404(cemetery_id)
    data = request.get_json()
    
    if not data or not data.get('blueprint_path') or not data.get('reference_points'):
        return jsonify({'error': 'Blueprint path and reference points are required'}), 400
    
    # Prepare cemetery data
    cemetery_data = {
        'id': cemetery.id,
        'name': cemetery.name,
        'location': cemetery.location
    }
    
    # Create blueprint overlay
    map_path = map_manager.setup_blueprint_overlay(
        cemetery_data,
        data['blueprint_path'],
        data['reference_points']
    )
    
    if map_path:
        return jsonify({
            'success': True,
            'map_path': map_path,
            'message': f'Blueprint overlay created for {cemetery.name}'
        })
    else:
        return jsonify({'error': 'Failed to create blueprint overlay'}), 400

@app.route('/api/export/google-maps/<int:cemetery_id>', methods=['GET'])
def export_google_maps(cemetery_id):
    """Export cemetery data for Google My Maps"""
    cemetery = Cemetery.query.get_or_404(cemetery_id)
    plots = Plot.query.filter_by(cemetery_id=cemetery_id).all()
    
    # Create KML data for Google My Maps
    kml_data = {
        'name': cemetery.name,
        'description': cemetery.description or '',
        'plots': []
    }
    
    for plot in plots:
        if plot.latitude and plot.longitude:
            plot_data = {
                'name': plot.plot_number,
                'latitude': plot.latitude,
                'longitude': plot.longitude,
                'individuals': [{
                    'name': i.name,
                    'born_date': i.born_date.isoformat() if i.born_date else None,
                    'died_date': i.died_date.isoformat() if i.died_date else None,
                    'epitaph': i.epitaph
                } for i in plot.individuals]
            }
            kml_data['plots'].append(plot_data)
    
    return jsonify(kml_data)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
