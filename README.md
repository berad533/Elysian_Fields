# Elysian Fields - Cemetery Management System

A comprehensive cemetery management system with OCR processing, backend synchronization, and Google Maps integration.

## System Overview

The Elysian Fields system consists of:

1. **Backend Server** - Flask-based API for data management
2. **Elysian Scribe** - Desktop application for photo processing and data entry
3. **Mobile Client** - Python client for Android integration
4. **Web Interface** - HTML/CSS/JS frontend for data visualization

## Features

### Core Functionality
- **OCR Processing** - Extract text from headstone photos using Tesseract
- **Image Straightening** - Correct skewed photos for better OCR accuracy
- **Multi-Person Support** - Handle family plots with multiple individuals
- **Backend Synchronization** - Real-time data sync with central database
- **File Upload Support** - Photos, 360° images, KMZ/KML files, blueprints
- **Searchable Database** - Full-text search across all cemetery data
- **Google Maps Integration** - Export data for Google My Maps visualization

### Workflow Support
- **Cemetery Setup** - Create and manage multiple cemeteries
- **Plot Management** - Organize graves by section, row, and plot number
- **Photo Processing** - Batch upload and OCR processing
- **Data Validation** - Ensure data quality and completeness
- **Export Options** - CSV, KML, and Google Maps formats

## Installation

### Prerequisites
- Python 3.8 or higher
- Tesseract OCR installed on your system
- Git (for version control)

### Backend Setup

1. **Install Python dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp env_example.txt .env
   # Edit .env with your configuration
   ```

3. **Start the backend server:**
   ```bash
   python start_backend.py
   ```

The backend will be available at `http://localhost:5000`

### Desktop Application Setup

1. **Install additional dependencies:**
   ```bash
   pip install customtkinter opencv-python numpy pandas requests
   ```

2. **Run the Elysian Scribe:**
   ```bash
   python elysian_scribe_backend_integrated.py
   ```

## Usage

### 1. Setting Up a Cemetery

1. Start the backend server
2. Open Elysian Scribe
3. Click "New Cemetery" to create a cemetery
4. Enter cemetery name, location, and description

### 2. Processing Headstone Photos

1. **Load Images:**
   - Click "Load Headstones" to select a directory of photos
   - Images will appear in the Image Navigator

2. **Straighten Images (Optional):**
   - Click "Straighten Image" to enter straightening mode
   - Click two points to define a line to straighten
   - Image will be automatically rotated

3. **Extract Text:**
   - Click and drag to select text area
   - Click "Run OCR on Selection" to extract text
   - Review OCR results in the text box

4. **Enter Data:**
   - Fill in plot location
   - Add individuals with names, birth/death dates
   - Enter epitaph text
   - Use "[+ Add Person]" for multiple individuals

5. **Save Data:**
   - Click "Save to Backend" to sync with database
   - Or "Save Locally" for offline storage

### 3. Mobile Integration

Use the mobile client for Android devices:

```python
from backend.mobile_client import ElysianFieldsClient, MobileWorkflow

# Initialize client
client = ElysianFieldsClient("http://your-server:5000/api")

# Set up cemetery
workflow = MobileWorkflow(client)
cemetery_id = workflow.setup_cemetery("Oakwood Cemetery")

# Process headstone photo
individuals_data = [
    {
        "name": "John Smith",
        "born_date": "1920-01-15",
        "died_date": "1995-03-22",
        "epitaph": "Beloved husband and father"
    }
]
workflow.process_headstone_photo(cemetery_id, "A-123", "path/to/photo.jpg", individuals_data)
```

### 4. File Upload Support

The system supports various file types:

- **Photos:** JPG, PNG, BMP, TIFF (headstone photos, 360° images)
- **Maps:** KMZ, KML files for plot coordinates
- **Blueprints:** PDF, image files for cemetery layouts

### 5. Google Maps Integration

Export cemetery data for Google My Maps:

```python
# Export data for Google My Maps
kml_data = client.export_google_maps(cemetery_id)
```

## API Endpoints

### Cemeteries
- `GET /api/cemeteries` - List all cemeteries
- `POST /api/cemeteries` - Create new cemetery
- `GET /api/cemeteries/{id}/plots` - Get plots for cemetery

### Plots
- `POST /api/cemeteries/{id}/plots` - Create new plot
- `POST /api/plots/{id}/individuals` - Add individual to plot
- `POST /api/plots/{id}/photos` - Upload photo for plot

### Files
- `POST /api/cemeteries/{id}/blueprints` - Upload blueprint
- `POST /api/cemeteries/{id}/import-kmz` - Import KMZ/KML file

### Search & Export
- `GET /api/search?q={query}` - Search across all data
- `GET /api/export/google-maps/{id}` - Export for Google Maps

## Database Schema

### Cemeteries
- `id` - Primary key
- `name` - Cemetery name
- `location` - Physical location
- `description` - Additional details

### Plots
- `id` - Primary key
- `cemetery_id` - Foreign key to cemetery
- `plot_number` - Plot identifier
- `section` - Cemetery section
- `row` - Row within section
- `latitude` - GPS latitude
- `longitude` - GPS longitude

### Individuals
- `id` - Primary key
- `plot_id` - Foreign key to plot
- `name` - Full name
- `born_date` - Birth date
- `died_date` - Death date
- `epitaph` - Memorial text
- `relationship` - Family relationship

### Photos
- `id` - Primary key
- `plot_id` - Foreign key to plot
- `filename` - Original filename
- `file_path` - Storage path
- `photo_type` - Type (headstone, 360, blueprint)
- `ocr_text` - Extracted text
- `ocr_confidence` - OCR confidence score

## Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
FLASK_DEBUG=True

# Database Configuration
DATABASE_URL=sqlite:///elysian_fields.db

# Tesseract OCR Configuration
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe

# Google Maps API (optional)
GOOGLE_MAPS_API_KEY=your-google-maps-api-key-here
```

### Tesseract Installation

**Windows:**
1. Download Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location: `C:\Program Files\Tesseract-OCR\`
3. Update `TESSERACT_PATH` in your `.env` file

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

## Troubleshooting

### Common Issues

1. **Backend Connection Failed:**
   - Ensure backend server is running on port 5000
   - Check firewall settings
   - Verify network connectivity

2. **OCR Not Working:**
   - Verify Tesseract installation
   - Check TESSERACT_PATH in configuration
   - Ensure image files are readable

3. **File Upload Errors:**
   - Check file size limits (500MB default)
   - Verify file permissions
   - Ensure upload directory exists

4. **Database Errors:**
   - Check database file permissions
   - Verify SQLite installation
   - Review database schema migrations

### Performance Optimization

1. **Image Processing:**
   - Resize large images before processing
   - Use appropriate image formats (JPG for photos, PNG for text)
   - Batch process multiple images

2. **Database Performance:**
   - Index frequently searched columns
   - Use connection pooling for high traffic
   - Regular database maintenance

3. **OCR Accuracy:**
   - Use high-resolution images
   - Straighten skewed images
   - Select specific text regions
   - Consider image preprocessing

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the API documentation

## Roadmap

### Planned Features
- [ ] Web-based admin interface
- [ ] Advanced image preprocessing
- [ ] Machine learning for name extraction
- [ ] Mobile app (React Native)
- [ ] Cloud deployment options
- [ ] Advanced reporting and analytics
- [ ] Integration with genealogy databases
- [ ] QR code generation for plots
- [ ] Automated plot mapping from photos
- [ ] Multi-language OCR support

### Version History
- **v2.0** - Backend integration, mobile client, Google Maps export
- **v1.3** - Image straightening, improved navigation
- **v1.1** - Multi-person support, enhanced data entry
- **v1.0** - Initial release with basic OCR functionality
