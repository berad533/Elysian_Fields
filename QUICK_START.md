# 🏛️ Elysian Fields - Quick Start Guide

## One-Command Startup

To start the complete Elysian Fields system (backend + desktop app):

```bash
python run_elysian_fields.py
```

That's it! This single command will:
- ✅ Install all dependencies
- ✅ Start the backend server
- ✅ Launch the desktop application
- ✅ Handle everything automatically

## Alternative Startup Options

### Option 1: Full Interactive Startup
```bash
python start_elysian_fields.py
```
This gives you menu options to choose what to start.

### Option 2: Windows Batch File
```bash
start_elysian_fields.bat
```
Double-click this file on Windows.

### Option 3: Manual Startup
```bash
# Terminal 1: Start backend
cd backend
python app.py

# Terminal 2: Start desktop app
python elysian_scribe_backend_integrated.py
```

## What You Get

### 🖥️ Desktop Application (Elysian Scribe)
- **GPS Location Setup**: Enter cemetery address to get GPS coordinates
- **Google Earth Import**: Import KMZ/KML files with plot data
- **Interactive Maps**: Create web-based maps with plot markers
- **OCR Processing**: Extract text from gravestone photos
- **Image Straightening**: Fix crooked photos
- **Multi-Person Support**: Handle multiple individuals per plot
- **Real-time Sync**: All data syncs to backend database

### 🌐 Backend API
- **REST API**: Full API for mobile/web clients
- **Database**: SQLite database with all cemetery data
- **File Upload**: Handle photos, blueprints, KMZ files
- **Google Maps Integration**: GPS coordinates and mapping
- **Search**: Search graves and plots
- **Export**: Export to Google My Maps format

### 🗺️ Google Maps Features
- **GPS Lookup**: Automatic coordinate finding from addresses
- **Google Earth Import**: Import plot data from KMZ files
- **Interactive Maps**: Web-based maps with plot markers
- **Blueprint Overlay**: Overlay cemetery blueprints on maps
- **Google My Maps Export**: Export data for Google My Maps

## Your Complete Workflow

1. **📱 Take Photos** with your Android device
2. **🗺️ Import GPS Data** from Google Earth KMZ files  
3. **📍 Setup Cemetery Location** with automatic GPS lookup
4. **🖼️ Upload Blueprints** and align with GPS coordinates
5. **🔍 Process Photos** with OCR and image straightening
6. **💾 Sync to Database** with real-time backend integration
7. **🌍 Export to Google My Maps** for public visualization
8. **🗺️ View Interactive Maps** in your browser

## System Requirements

- Python 3.8+
- Windows 10/11 (tested)
- Internet connection (for GPS lookup and maps)
- Tesseract OCR (for text extraction)

## Troubleshooting

### Backend Won't Start
```bash
cd backend
python app.py
```

### Dependencies Missing
```bash
pip install -r requirements_complete.txt
```

### Desktop App Issues
```bash
python elysian_scribe_backend_integrated.py
```

## Support

The system includes:
- ✅ Complete backend API
- ✅ Desktop GUI application  
- ✅ Google Maps integration
- ✅ OCR text extraction
- ✅ Image processing
- ✅ Database management
- ✅ File upload handling
- ✅ Export capabilities

**Everything works with a single command: `python run_elysian_fields.py`**
