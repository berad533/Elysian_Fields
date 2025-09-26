"""
Elysian Scribe v2.0 - Backend Integrated Version
A desktop application for processing cemetery headstone photos with backend synchronization

Dependencies:
- customtkinter
- pillow (PIL)
- numpy
- opencv-python
- pytesseract
- pandas
- requests

Author: Project Elysian Fields Development Team
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import pytesseract
import pandas as pd
import numpy as np
import cv2
import os
import requests
import json
from pathlib import Path
import tkinter as tk
import math
from datetime import datetime

# TESSERACT CONFIGURATION
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Backend API Configuration
BACKEND_URL = "http://localhost:5000/api"

# Set appearance mode and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class PersonFrame:
    """Class to represent a single person's data entry frame"""
    
    def __init__(self, parent_frame, person_number):
        self.parent_frame = parent_frame
        self.person_number = person_number
        self.frame = None
        self.name_entry = None
        self.born_entry = None
        self.died_entry = None
        self.remove_btn = None
        self.create_widgets()
    
    def create_widgets(self):
        """Create the widgets for this person frame"""
        # Create the main frame for this person
        self.frame = ctk.CTkFrame(self.parent_frame)
        self.frame.pack(fill="x", padx=5, pady=5)
        
        # Person header with remove button
        header_frame = ctk.CTkFrame(self.frame)
        header_frame.pack(fill="x", padx=5, pady=(5, 0))
        header_frame.grid_columnconfigure(0, weight=1)
        
        person_label = ctk.CTkLabel(header_frame, text=f"Person {self.person_number}", 
                                  font=ctk.CTkFont(size=12, weight="bold"))
        person_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        # Remove button (only show if more than one person)
        if self.person_number > 1:
            self.remove_btn = ctk.CTkButton(
                header_frame, 
                text="Remove", 
                width=60, 
                height=25,
                fg_color="red",
                hover_color="darkred",
                command=self.remove_person
            )
            self.remove_btn.grid(row=0, column=1, padx=5, pady=5)
        
        # Name entry
        name_label = ctk.CTkLabel(self.frame, text="Name:")
        name_label.pack(anchor="w", padx=10, pady=(5, 0))
        self.name_entry = ctk.CTkEntry(self.frame, width=200)
        self.name_entry.pack(fill="x", padx=10, pady=(0, 5))
        
        # Born entry
        born_label = ctk.CTkLabel(self.frame, text="Born:")
        born_label.pack(anchor="w", padx=10)
        self.born_entry = ctk.CTkEntry(self.frame, width=200)
        self.born_entry.pack(fill="x", padx=10, pady=(0, 5))
        
        # Died entry
        died_label = ctk.CTkLabel(self.frame, text="Died:")
        died_label.pack(anchor="w", padx=10)
        self.died_entry = ctk.CTkEntry(self.frame, width=200)
        self.died_entry.pack(fill="x", padx=10, pady=(0, 5))
    
    def remove_person(self):
        """Remove this person frame from the parent"""
        if self.frame:
            self.frame.destroy()
    
    def get_data(self):
        """Get the data from this person frame"""
        return {
            'name': self.name_entry.get().strip() if self.name_entry else '',
            'born': self.born_entry.get().strip() if self.born_entry else '',
            'died': self.died_entry.get().strip() if self.died_entry else ''
        }
    
    def clear_data(self):
        """Clear all data in this person frame"""
        if self.name_entry:
            self.name_entry.delete(0, "end")
        if self.born_entry:
            self.born_entry.delete(0, "end")
        if self.died_entry:
            self.died_entry.delete(0, "end")

class BackendAPI:
    """Backend API client for Elysian Scribe"""
    
    def __init__(self, base_url=BACKEND_URL):
        self.base_url = base_url
        self.session = requests.Session()
    
    def health_check(self):
        """Check if backend is running"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False
    
    def get_cemeteries(self):
        """Get all cemeteries"""
        try:
            response = self.session.get(f"{self.base_url}/cemeteries")
            return response.json() if response.status_code == 200 else []
        except:
            return []
    
    def create_cemetery(self, name, location="", description=""):
        """Create a new cemetery"""
        try:
            data = {"name": name, "location": location, "description": description}
            response = self.session.post(f"{self.base_url}/cemeteries", json=data)
            return response.json() if response.status_code == 201 else None
        except:
            return None
    
    def create_plot(self, cemetery_id, plot_number, section="", row="", latitude=None, longitude=None):
        """Create a new plot"""
        try:
            data = {
                "plot_number": plot_number,
                "section": section,
                "row": row,
                "latitude": latitude,
                "longitude": longitude
            }
            response = self.session.post(f"{self.base_url}/cemeteries/{cemetery_id}/plots", json=data)
            return response.json() if response.status_code == 201 else None
        except:
            return None
    
    def add_individual(self, plot_id, name, born_date=None, died_date=None, epitaph="", relationship=""):
        """Add an individual to a plot"""
        try:
            data = {
                "name": name,
                "born_date": born_date,
                "died_date": died_date,
                "epitaph": epitaph,
                "relationship": relationship
            }
            response = self.session.post(f"{self.base_url}/plots/{plot_id}/individuals", json=data)
            return response.json() if response.status_code == 201 else None
        except:
            return None
    
    def upload_photo(self, plot_id, image_path, photo_type="headstone"):
        """Upload a photo for a plot"""
        try:
            with open(image_path, 'rb') as f:
                files = {'file': f}
                data = {'photo_type': photo_type}
                response = self.session.post(f"{self.base_url}/plots/{plot_id}/photos", files=files, data=data)
            return response.json() if response.status_code == 201 else None
        except:
            return None

class ElysianScribe:
    def __init__(self):
        """Initialize the Elysian Scribe application"""
        self.root = ctk.CTk()
        self.root.title("Elysian Scribe v2.0 - Backend Integrated")
        self.root.geometry("1600x900")
        self.root.minsize(1400, 800)
        
        # Initialize backend API
        self.api = BackendAPI()
        self.backend_connected = self.api.health_check()
        
        # Application state variables
        self.current_image_index = 0
        self.image_files = []
        self.current_image = None
        self.current_photo = None
        self.original_image = None
        self.map_image = None
        self.map_photo = None
        self.current_cemetery = None
        self.current_plot = None
        
        # Selection rectangle variables
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        
        # Straightening mode variables
        self.straightening_mode = False
        self.straightening_points = []
        self.straightening_lines = []
        
        # Person frames management
        self.person_frames = []
        self.person_counter = 1
        
        # Data storage
        self.data_records = []
        self.data_columns = ['image_filename', 'plot_location', 'name', 'born', 'died', 'epitaph', 'ocr_text']
        
        # Initialize the GUI
        self.setup_gui()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_gui(self):
        """Set up the main GUI layout"""
        # Configure grid weights for responsive layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_columnconfigure(2, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Create the three main frames
        self.create_left_frame()
        self.create_center_frame()
        self.create_right_frame()
    
    def create_left_frame(self):
        """Create the left frame for cemetery and map management"""
        self.left_frame = ctk.CTkFrame(self.root)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(2, weight=1)
        
        # Backend status
        status_color = "green" if self.backend_connected else "red"
        status_text = "Backend Connected" if self.backend_connected else "Backend Disconnected"
        self.backend_status = ctk.CTkLabel(
            self.left_frame, 
            text=status_text, 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=status_color
        )
        self.backend_status.grid(row=0, column=0, pady=(10, 5))
        
        # Cemetery selection
        cemetery_label = ctk.CTkLabel(self.left_frame, text="Cemetery:", font=ctk.CTkFont(size=14, weight="bold"))
        cemetery_label.grid(row=1, column=0, pady=(10, 5), sticky="w", padx=10)
        
        self.cemetery_var = ctk.StringVar()
        self.cemetery_dropdown = ctk.CTkComboBox(
            self.left_frame, 
            variable=self.cemetery_var,
            command=self.on_cemetery_selected,
            width=200
        )
        self.cemetery_dropdown.grid(row=2, column=0, padx=10, pady=5)
        
        # New cemetery button
        self.new_cemetery_btn = ctk.CTkButton(
            self.left_frame, 
            text="New Cemetery", 
            command=self.create_new_cemetery,
            width=200
        )
        self.new_cemetery_btn.grid(row=3, column=0, pady=5)
        
        # Setup location button
        self.setup_location_btn = ctk.CTkButton(
            self.left_frame, 
            text="Setup GPS Location", 
            command=self.setup_cemetery_location,
            width=200,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.setup_location_btn.grid(row=4, column=0, pady=5)
        
        # Import Google Earth button
        self.import_google_earth_btn = ctk.CTkButton(
            self.left_frame, 
            text="Import Google Earth", 
            command=self.import_google_earth_data,
            width=200,
            fg_color="orange",
            hover_color="darkorange"
        )
        self.import_google_earth_btn.grid(row=5, column=0, pady=5)
        
        # Create map button
        self.create_map_btn = ctk.CTkButton(
            self.left_frame, 
            text="Create Interactive Map", 
            command=self.create_cemetery_map,
            width=200,
            fg_color="blue",
            hover_color="darkblue"
        )
        self.create_map_btn.grid(row=6, column=0, pady=5)
        
        # Batch OCR button
        self.batch_ocr_btn = ctk.CTkButton(
            self.left_frame, 
            text="Auto Batch OCR", 
            command=self.auto_batch_ocr,
            width=200,
            fg_color="purple",
            hover_color="darkviolet"
        )
        self.batch_ocr_btn.grid(row=7, column=0, pady=5)
        
        # Map display area
        map_title = ctk.CTkLabel(self.left_frame, text="Cemetery Map", font=ctk.CTkFont(size=14, weight="bold"))
        map_title.grid(row=8, column=0, pady=(20, 5))
        
        # Map status indicator
        self.map_status_label = ctk.CTkLabel(
            self.left_frame, 
            text="📍 No GPS coordinates set",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.map_status_label.grid(row=9, column=0, pady=5)
        
        self.map_label = ctk.CTkLabel(self.left_frame, text="No map loaded", width=300, height=300)
        self.map_label.grid(row=5, column=0, padx=10, pady=5, sticky="nsew")
        
        # Load map button
        self.load_map_btn = ctk.CTkButton(
            self.left_frame, 
            text="Load Map", 
            command=self.load_map,
            width=200
        )
        self.load_map_btn.grid(row=6, column=0, pady=10)
        
        # Load cemeteries on startup
        self.load_cemeteries()
    
    def create_center_frame(self):
        """Create the center frame for image workstation"""
        self.center_frame = ctk.CTkFrame(self.root)
        self.center_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.center_frame.grid_columnconfigure(0, weight=1)
        self.center_frame.grid_rowconfigure(1, weight=1)
        
        # Image Navigator
        nav_title = ctk.CTkLabel(self.center_frame, text="Image Navigator", font=ctk.CTkFont(size=14, weight="bold"))
        nav_title.grid(row=0, column=0, pady=(10, 5), sticky="w", padx=10)
        
        self.image_navigator = ctk.CTkScrollableFrame(self.center_frame, width=500, height=100)
        self.image_navigator.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        # Image Viewer
        viewer_title = ctk.CTkLabel(self.center_frame, text="Image Viewer", font=ctk.CTkFont(size=14, weight="bold"))
        viewer_title.grid(row=2, column=0, pady=(10, 5), sticky="w", padx=10)
        
        # Canvas for image display and selection
        self.canvas = tk.Canvas(
            self.center_frame, 
            bg="gray20", 
            width=500, 
            height=400,
            highlightthickness=0
        )
        self.canvas.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")
        
        # Bind mouse events for selection and straightening
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.update_selection)
        self.canvas.bind("<ButtonRelease-1>", self.end_selection)
        
        # Control buttons frame
        controls_frame = ctk.CTkFrame(self.center_frame)
        controls_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_columnconfigure(1, weight=1)
        controls_frame.grid_columnconfigure(2, weight=1)
        
        # Load headstones button
        self.load_headstones_btn = ctk.CTkButton(
            controls_frame, 
            text="Load Headstones", 
            command=self.load_headstones,
            width=120
        )
        self.load_headstones_btn.grid(row=0, column=0, padx=5)
        
        # Straighten image button
        self.straighten_btn = ctk.CTkButton(
            controls_frame, 
            text="Straighten Image", 
            command=self.toggle_straightening_mode,
            width=120,
            fg_color="orange",
            hover_color="darkorange"
        )
        self.straighten_btn.grid(row=0, column=1, padx=5)
        
        # Instructions
        self.instructions_label = ctk.CTkLabel(
            controls_frame, 
            text="Click and drag to select text area for OCR",
            font=ctk.CTkFont(size=10)
        )
        self.instructions_label.grid(row=0, column=2, padx=5)
    
    def create_right_frame(self):
        """Create the right frame for data entry and controls"""
        self.right_frame = ctk.CTkFrame(self.root)
        self.right_frame.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        self.right_frame.grid_columnconfigure(0, weight=1)
        
        # Data entry title
        data_title = ctk.CTkLabel(self.right_frame, text="Data Entry", font=ctk.CTkFont(size=16, weight="bold"))
        data_title.grid(row=0, column=0, pady=(10, 5))
        
        # Plot Location
        ctk.CTkLabel(self.right_frame, text="Plot Location:").grid(row=1, column=0, sticky="w", padx=10, pady=(10, 0))
        self.plot_entry = ctk.CTkEntry(self.right_frame, width=250)
        self.plot_entry.grid(row=2, column=0, padx=10, pady=(0, 10))
        
        # Epitaph
        ctk.CTkLabel(self.right_frame, text="Epitaph:").grid(row=3, column=0, sticky="w", padx=10)
        self.epitaph_textbox = ctk.CTkTextbox(self.right_frame, width=250, height=60)
        self.epitaph_textbox.grid(row=4, column=0, padx=10, pady=(0, 10))
        
        # Individuals on this Plot section
        individuals_label = ctk.CTkLabel(self.right_frame, text="Individuals on this Plot:", 
                                       font=ctk.CTkFont(size=14, weight="bold"))
        individuals_label.grid(row=5, column=0, sticky="w", padx=10, pady=(10, 5))
        
        # Scrollable frame for person entries
        self.persons_scrollable_frame = ctk.CTkScrollableFrame(self.right_frame, width=250, height=150)
        self.persons_scrollable_frame.grid(row=6, column=0, padx=10, pady=(0, 10), sticky="nsew")
        
        # Add Person button
        self.add_person_btn = ctk.CTkButton(
            self.right_frame, 
            text="[+ Add Person]", 
            command=self.add_person,
            width=250,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.add_person_btn.grid(row=7, column=0, padx=10, pady=5)
        
        # OCR Results
        ctk.CTkLabel(self.right_frame, text="OCR Results:").grid(row=8, column=0, sticky="w", padx=10, pady=(10, 0))
        self.ocr_textbox = ctk.CTkTextbox(self.right_frame, width=250, height=60, state="disabled")
        self.ocr_textbox.grid(row=9, column=0, padx=10, pady=(0, 10))
        
        # Run OCR button
        self.run_ocr_btn = ctk.CTkButton(
            self.right_frame, 
            text="Run OCR on Selection", 
            command=self.run_ocr_on_selection,
            width=250
        )
        self.run_ocr_btn.grid(row=10, column=0, padx=10, pady=10)
        
        # Navigation buttons
        nav_frame = ctk.CTkFrame(self.right_frame)
        nav_frame.grid(row=11, column=0, padx=10, pady=10, sticky="ew")
        nav_frame.grid_columnconfigure(0, weight=1)
        nav_frame.grid_columnconfigure(1, weight=1)
        
        self.prev_btn = ctk.CTkButton(nav_frame, text="Previous", command=self.previous_image, width=100)
        self.prev_btn.grid(row=0, column=0, padx=5)
        
        self.next_btn = ctk.CTkButton(nav_frame, text="Next", command=self.next_image, width=100)
        self.next_btn.grid(row=0, column=1, padx=5)
        
        # Save records button
        self.save_btn = ctk.CTkButton(
            self.right_frame, 
            text="Save to Backend", 
            command=self.save_to_backend,
            width=250,
            fg_color="blue"
        )
        self.save_btn.grid(row=12, column=0, padx=10, pady=10)
        
        # Local save button
        self.local_save_btn = ctk.CTkButton(
            self.right_frame, 
            text="Save Locally", 
            command=self.save_records,
            width=250,
            fg_color="gray"
        )
        self.local_save_btn.grid(row=13, column=0, padx=10, pady=5)
        
        # Status label
        self.status_label = ctk.CTkLabel(self.right_frame, text="No images loaded", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=14, column=0, pady=10)
        
        # Initialize with one person frame
        self.add_person()
    
    def load_cemeteries(self):
        """Load cemeteries from backend"""
        if not self.backend_connected:
            return
        
        cemeteries = self.api.get_cemeteries()
        cemetery_names = [c['name'] for c in cemeteries]
        self.cemetery_dropdown.configure(values=cemetery_names)
        
        if cemetery_names:
            self.cemetery_dropdown.set(cemetery_names[0])
            self.on_cemetery_selected(cemetery_names[0])
    
    def create_new_cemetery(self):
        """Create a new cemetery"""
        dialog = ctk.CTkInputDialog(
            text="Enter cemetery name:",
            title="New Cemetery"
        )
        cemetery_name = dialog.get_input()
        
        if cemetery_name and self.backend_connected:
            result = self.api.create_cemetery(cemetery_name)
            if result:
                messagebox.showinfo("Success", f"Created cemetery: {cemetery_name}")
                self.load_cemeteries()
            else:
                messagebox.showerror("Error", "Failed to create cemetery")
        elif not self.backend_connected:
            messagebox.showerror("Error", "Backend not connected")
    
    def setup_cemetery_location(self):
        """Setup GPS location for the selected cemetery"""
        if not self.current_cemetery:
            messagebox.showwarning("Warning", "Please select a cemetery first")
            return
        
        # Create a custom dialog for address input
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Setup GPS Location")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (300 // 2)
        dialog.geometry(f"500x300+{x}+{y}")
        
        # Address input
        ctk.CTkLabel(dialog, text="Enter cemetery address:", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        address_entry = ctk.CTkEntry(dialog, width=400, placeholder_text="e.g., 123 Cemetery Road, City, State")
        address_entry.pack(pady=10)
        
        # Manual coordinates option
        ctk.CTkLabel(dialog, text="OR enter GPS coordinates manually:", font=ctk.CTkFont(size=12)).pack(pady=(20,5))
        
        coord_frame = ctk.CTkFrame(dialog)
        coord_frame.pack(pady=10)
        
        ctk.CTkLabel(coord_frame, text="Latitude:").grid(row=0, column=0, padx=5, pady=5)
        lat_entry = ctk.CTkEntry(coord_frame, width=150, placeholder_text="e.g., 40.7128")
        lat_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ctk.CTkLabel(coord_frame, text="Longitude:").grid(row=0, column=2, padx=5, pady=5)
        lng_entry = ctk.CTkEntry(coord_frame, width=150, placeholder_text="e.g., -74.0060")
        lng_entry.grid(row=0, column=3, padx=5, pady=5)
        
        # Buttons
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(pady=20)
        
        def lookup_address():
            address = address_entry.get().strip()
            if not address:
                messagebox.showwarning("Warning", "Please enter an address")
                return
            
            # Show progress
            progress_label = ctk.CTkLabel(dialog, text="Looking up GPS coordinates...", font=ctk.CTkFont(size=12))
            progress_label.pack(pady=5)
            dialog.update()
            
            if self.backend_connected:
                try:
                    response = self.api.session.post(
                        f"{self.api.base_url}/cemeteries/{self.current_cemetery['id']}/setup-location",
                        json={'address': address},
                        timeout=30  # Add timeout
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        messagebox.showinfo("Success", data['message'])
                        self.load_cemeteries()  # Refresh cemetery list
                        
                        # Automatically create and load the map
                        self.auto_create_map()
                        
                        dialog.destroy()
                    else:
                        try:
                            error_data = response.json()
                            error_msg = error_data.get('error', 'Failed to setup location')
                            suggestion = error_data.get('suggestion', '')
                            if suggestion:
                                error_msg += f"\n\nSuggestion: {suggestion}"
                            messagebox.showerror("Error", error_msg)
                        except:
                            messagebox.showerror("Error", f"Failed to setup location (Status: {response.status_code})")
                        progress_label.destroy()
                except requests.exceptions.ConnectionError:
                    messagebox.showerror("Error", "Cannot connect to backend server. Please make sure the backend is running.")
                    progress_label.destroy()
                except requests.exceptions.Timeout:
                    messagebox.showerror("Error", "Request timed out. The geocoding service may be slow. Please try again or use manual coordinates.")
                    progress_label.destroy()
                except Exception as e:
                    error_msg = str(e)
                    if "expecting value" in error_msg.lower():
                        messagebox.showerror("Error", "GPS lookup failed due to a network issue. Please try again or use manual coordinates.")
                    else:
                        messagebox.showerror("Error", f"Failed to setup location: {error_msg}")
                    progress_label.destroy()
            else:
                messagebox.showerror("Error", "Backend not connected. Please start the backend server first.")
                progress_label.destroy()
        
        def use_manual_coords():
            lat = lat_entry.get().strip()
            lng = lng_entry.get().strip()
            
            if not lat or not lng:
                messagebox.showwarning("Warning", "Please enter both latitude and longitude")
                return
            
            try:
                lat_float = float(lat)
                lng_float = float(lng)
                
                if self.backend_connected:
                    # Update cemetery with manual coordinates
                    response = self.api.session.put(
                        f"{self.api.base_url}/cemeteries/{self.current_cemetery['id']}",
                        json={
                            'latitude': lat_float,
                            'longitude': lng_float
                        }
                    )
                    
                    if response.status_code == 200:
                        messagebox.showinfo("Success", f"GPS coordinates set to {lat_float}, {lng_float}")
                        self.load_cemeteries()  # Refresh cemetery list
                        
                        # Automatically create and load the map
                        self.auto_create_map()
                        
                        dialog.destroy()
                    else:
                        error_data = response.json()
                        messagebox.showerror("Error", error_data.get('error', 'Failed to update coordinates'))
                else:
                    messagebox.showerror("Error", "Backend not connected")
                    
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers for latitude and longitude")
        
        ctk.CTkButton(button_frame, text="Lookup Address", command=lookup_address, width=150).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Use Manual Coords", command=use_manual_coords, width=150).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=dialog.destroy, width=100).pack(side="left", padx=5)
    
    def import_google_earth_data(self):
        """Import plot data from Google Earth KMZ file"""
        if not self.current_cemetery:
            messagebox.showwarning("Warning", "Please select a cemetery first")
            return
        
        file_path = filedialog.askopenfilename(
            title="Select Google Earth KMZ/KML File",
            filetypes=[("KMZ files", "*.kmz"), ("KML files", "*.kml")]
        )
        
        if file_path and self.backend_connected:
            try:
                with open(file_path, 'rb') as f:
                    files = {'file': f}
                    response = self.api.session.post(
                        f"{self.api.base_url}/cemeteries/{self.current_cemetery['id']}/import-google-earth",
                        files=files
                    )
                
                if response.status_code == 200:
                    data = response.json()
                    messagebox.showinfo("Success", data['message'])
                else:
                    error_data = response.json()
                    messagebox.showerror("Error", error_data.get('error', 'Failed to import Google Earth data'))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import Google Earth data: {str(e)}")
        elif not self.backend_connected:
            messagebox.showerror("Error", "Backend not connected")
    
    def create_cemetery_map(self):
        """Create an interactive map for the cemetery"""
        if not self.current_cemetery:
            messagebox.showwarning("Warning", "Please select a cemetery first")
            return
        
        if self.backend_connected:
            try:
                response = self.api.session.post(
                    f"{self.api.base_url}/cemeteries/{self.current_cemetery['id']}/create-map"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    messagebox.showinfo("Success", f"Map created: {data['map_path']}")
                    
                    # Ask if user wants to open the map
                    if messagebox.askyesno("Open Map", "Would you like to open the interactive map in your browser?"):
                        import webbrowser
                        webbrowser.open(f"file://{os.path.abspath(data['map_path'])}")
                else:
                    error_data = response.json()
                    messagebox.showerror("Error", error_data.get('error', 'Failed to create map'))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create map: {str(e)}")
        else:
            messagebox.showerror("Error", "Backend not connected")
    
    def auto_create_map(self):
        """Automatically create and display map after GPS setup"""
        if not self.current_cemetery or not self.backend_connected:
            return
        
        try:
            # Create the map
            response = self.api.session.post(
                f"{self.api.base_url}/cemeteries/{self.current_cemetery['id']}/create-map"
            )
            
            if response.status_code == 200:
                data = response.json()
                map_path = data['map_path']
                
                # Ask if user wants to open the map
                if messagebox.askyesno("Map Created", 
                                     f"Interactive map created successfully!\n\nWould you like to open it in your browser?"):
                    import webbrowser
                    webbrowser.open(f"file://{os.path.abspath(map_path)}")
                
                # Update the map display in the desktop app
                self.update_map_display(map_path)
                
                # Update map status
                if self.current_cemetery.get('latitude') and self.current_cemetery.get('longitude'):
                    self.map_status_label.configure(
                        text=f"📍 GPS: {self.current_cemetery['latitude']:.4f}, {self.current_cemetery['longitude']:.4f}",
                        text_color="green"
                    )
                
            else:
                print("Failed to create map automatically")
                
        except Exception as e:
            print(f"Error creating map automatically: {e}")
    
    def update_map_display(self, map_path):
        """Update the map display in the desktop app"""
        try:
            # Create a simple map preview or link
            if hasattr(self, 'map_display_label'):
                self.map_display_label.destroy()
            
            # Create map display area
            self.map_display_label = ctk.CTkLabel(
                self.left_frame,
                text=f"🗺️ Map Created!\nClick to open in browser",
                font=ctk.CTkFont(size=12),
                cursor="hand2",
                text_color="blue"
            )
            self.map_display_label.grid(row=10, column=0, pady=10)
            
            # Make it clickable
            def open_map():
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(map_path)}")
            
            self.map_display_label.bind("<Button-1>", lambda e: open_map())
            
        except Exception as e:
            print(f"Error updating map display: {e}")
    
    def auto_batch_ocr(self):
        """Automatically process all images in a folder with OCR and create database"""
        if not self.current_cemetery:
            messagebox.showwarning("Warning", "Please select a cemetery first")
            return
        
        # Select folder with images
        folder_path = filedialog.askdirectory(
            title="Select folder containing gravestone images"
        )
        
        if not folder_path:
            return
        
        # Get all image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        image_files = []
        
        for file in os.listdir(folder_path):
            if Path(file).suffix.lower() in image_extensions:
                image_files.append(os.path.join(folder_path, file))
        
        if not image_files:
            messagebox.showwarning("Warning", "No image files found in the selected folder")
            return
        
        # Create progress dialog
        progress_dialog = ctk.CTkToplevel(self.root)
        progress_dialog.title("Auto Batch OCR Progress")
        progress_dialog.geometry("500x400")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()
        
        # Center the dialog
        progress_dialog.update_idletasks()
        x = (progress_dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (progress_dialog.winfo_screenheight() // 2) - (400 // 2)
        progress_dialog.geometry(f"500x400+{x}+{y}")
        
        # Progress elements
        ctk.CTkLabel(progress_dialog, text="Auto Batch OCR Processing", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        progress_label = ctk.CTkLabel(progress_dialog, text=f"Processing {len(image_files)} images...")
        progress_label.pack(pady=5)
        
        progress_bar = ctk.CTkProgressBar(progress_dialog, width=400)
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        
        # Results textbox
        results_text = ctk.CTkTextbox(progress_dialog, width=450, height=200)
        results_text.pack(pady=10, padx=20, fill="both", expand=True)
        
        # Process images
        def process_images():
            results = []
            successful = 0
            failed = 0
            
            for i, image_path in enumerate(image_files):
                try:
                    # Update progress
                    progress = (i + 1) / len(image_files)
                    progress_bar.set(progress)
                    progress_label.configure(text=f"Processing {i+1}/{len(image_files)}: {os.path.basename(image_path)}")
                    progress_dialog.update()
                    
                    # Process image with OCR
                    result = self.process_single_image_ocr(image_path)
                    
                    if result:
                        successful += 1
                        results.append(f"✅ {os.path.basename(image_path)}: {result.get('name', 'Unknown')}")
                        
                        # Save to backend if connected
                        if self.backend_connected:
                            self.save_ocr_result_to_backend(result, image_path)
                    else:
                        failed += 1
                        results.append(f"❌ {os.path.basename(image_path)}: OCR failed")
                        
                except Exception as e:
                    failed += 1
                    results.append(f"❌ {os.path.basename(image_path)}: Error - {str(e)}")
            
            # Update results
            results_text.delete("1.0", "end")
            results_text.insert("1.0", f"Batch OCR Complete!\n\n")
            results_text.insert("end", f"✅ Successful: {successful}\n")
            results_text.insert("end", f"❌ Failed: {failed}\n\n")
            results_text.insert("end", "Results:\n")
            results_text.insert("end", "\n".join(results))
            
            progress_label.configure(text=f"Complete! {successful} successful, {failed} failed")
            
            # Add close button
            close_btn = ctk.CTkButton(progress_dialog, text="Close", 
                                    command=progress_dialog.destroy, width=100)
            close_btn.pack(pady=10)
        
        # Start processing in a separate thread
        import threading
        processing_thread = threading.Thread(target=process_images)
        processing_thread.daemon = True
        processing_thread.start()
    
    def process_single_image_ocr(self, image_path):
        """Process a single image with OCR and return extracted data"""
        try:
            # Load image
            image = Image.open(image_path)
            
            # Run OCR on entire image
            extracted_text = pytesseract.image_to_string(image)
            
            if not extracted_text.strip():
                return None
            
            # Parse the text to extract name, dates, etc.
            parsed_data = self.parse_ocr_text(extracted_text)
            
            return {
                'image_path': image_path,
                'extracted_text': extracted_text,
                'name': parsed_data.get('name', 'Unknown'),
                'born_date': parsed_data.get('born_date'),
                'died_date': parsed_data.get('died_date'),
                'epitaph': parsed_data.get('epitaph', '')
            }
            
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return None
    
    def parse_ocr_text(self, text):
        """Parse OCR text to extract structured data"""
        import re
        
        # Clean up text
        text = text.strip()
        
        # Try to extract name (usually the first line or largest text)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        name = lines[0] if lines else 'Unknown'
        
        # Try to extract dates
        date_pattern = r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})\b'
        dates = re.findall(date_pattern, text)
        
        born_date = None
        died_date = None
        
        if len(dates) >= 2:
            # Assume first date is birth, second is death
            born_date = dates[0]
            died_date = dates[1]
        elif len(dates) == 1:
            # Only one date, assume it's death date
            died_date = dates[0]
        
        # Extract epitaph (everything after the main text)
        epitaph = ''
        if len(lines) > 2:
            epitaph = ' '.join(lines[2:])
        
        return {
            'name': name,
            'born_date': born_date,
            'died_date': died_date,
            'epitaph': epitaph
        }
    
    def save_ocr_result_to_backend(self, result, image_path):
        """Save OCR result to backend database"""
        if not self.backend_connected or not self.current_cemetery:
            return
        
        try:
            # Create a plot for this image
            plot_data = {
                'plot_number': f"AUTO-{os.path.basename(image_path)}",
                'section': 'Auto-OCR',
                'row': 'Batch'
            }
            
            # Create plot
            plot_response = self.api.session.post(
                f"{self.api.base_url}/cemeteries/{self.current_cemetery['id']}/plots",
                json=plot_data
            )
            
            if plot_response.status_code == 201:
                plot_id = plot_response.json()['id']
                
                # Add individual
                individual_data = {
                    'name': result['name'],
                    'born_date': result['born_date'],
                    'died_date': result['died_date'],
                    'epitaph': result['epitaph']
                }
                
                individual_response = self.api.session.post(
                    f"{self.api.base_url}/plots/{plot_id}/individuals",
                    json=individual_data
                )
                
                if individual_response.status_code == 201:
                    print(f"✅ Saved {result['name']} to database")
                else:
                    print(f"❌ Failed to save individual: {individual_response.text}")
            else:
                print(f"❌ Failed to create plot: {plot_response.text}")
                
        except Exception as e:
            print(f"❌ Error saving to backend: {e}")
    
    def on_cemetery_selected(self, cemetery_name):
        """Handle cemetery selection"""
        if not self.backend_connected:
            return
        
        cemeteries = self.api.get_cemeteries()
        self.current_cemetery = next((c for c in cemeteries if c['name'] == cemetery_name), None)
        
        if self.current_cemetery:
            print(f"Selected cemetery: {cemetery_name} (ID: {self.current_cemetery['id']})")
            
            # Update map status
            if self.current_cemetery.get('latitude') and self.current_cemetery.get('longitude'):
                self.map_status_label.configure(
                    text=f"📍 GPS: {self.current_cemetery['latitude']:.4f}, {self.current_cemetery['longitude']:.4f}",
                    text_color="green"
                )
            else:
                self.map_status_label.configure(
                    text="📍 No GPS coordinates set",
                    text_color="gray"
                )
    
    def add_person(self):
        """Add a new person frame to the scrollable frame"""
        person_frame = PersonFrame(self.persons_scrollable_frame, self.person_counter)
        self.person_frames.append(person_frame)
        self.person_counter += 1
        
        # Update remove buttons visibility
        self.update_remove_buttons()
    
    def update_remove_buttons(self):
        """Update the visibility of remove buttons based on number of person frames"""
        for i, person_frame in enumerate(self.person_frames):
            if person_frame.remove_btn:
                # Show remove button only if there's more than one person
                if len(self.person_frames) > 1:
                    person_frame.remove_btn.grid(row=0, column=1, padx=5, pady=5)
                else:
                    person_frame.remove_btn.grid_remove()
    
    def load_map(self):
        """Load and display a cemetery map image"""
        file_path = filedialog.askopenfilename(
            title="Select Cemetery Map",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        
        if file_path:
            try:
                self.map_image = Image.open(file_path)
                # Resize map to fit the label while maintaining aspect ratio
                self.map_image.thumbnail((300, 300), Image.Resampling.LANCZOS)
                self.map_photo = ImageTk.PhotoImage(self.map_image)
                self.map_label.configure(image=self.map_photo, text="")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load map: {str(e)}")
    
    def load_headstones(self):
        """Load headstone images from a directory"""
        directory = filedialog.askdirectory(title="Select Headstone Images Directory")
        
        if directory:
            # Get all image files from the directory
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
            self.image_files = []
            
            for file_path in Path(directory).iterdir():
                if file_path.suffix.lower() in image_extensions:
                    self.image_files.append(file_path)
            
            if self.image_files:
                self.current_image_index = 0
                self.populate_image_navigator()
                self.load_current_image()
                self.update_status()
                messagebox.showinfo("Success", f"Loaded {len(self.image_files)} headstone images")
            else:
                messagebox.showwarning("Warning", "No image files found in the selected directory")
    
    def populate_image_navigator(self):
        """Populate the image navigator with clickable image names"""
        # Clear existing navigator content
        for widget in self.image_navigator.winfo_children():
            widget.destroy()
        
        # Add clickable buttons for each image
        for i, image_path in enumerate(self.image_files):
            btn = ctk.CTkButton(
                self.image_navigator,
                text=image_path.name,
                command=lambda idx=i: self.select_image_by_index(idx),
                width=400,
                height=25,
                fg_color="gray" if i != self.current_image_index else "blue"
            )
            btn.pack(fill="x", padx=5, pady=2)
    
    def select_image_by_index(self, index):
        """Select an image by its index in the navigator"""
        if 0 <= index < len(self.image_files):
            self.current_image_index = index
            self.load_current_image()
            self.update_status()
            self.populate_image_navigator()  # Refresh to update button colors
            self.clear_form()
    
    def load_current_image(self):
        """Load and display the current headstone image"""
        if not self.image_files or self.current_image_index >= len(self.image_files):
            return
        
        try:
            image_path = self.image_files[self.current_image_index]
            self.original_image = Image.open(image_path)
            self.current_image = self.original_image.copy()
            
            # Resize image to fit canvas while maintaining aspect ratio
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
                # Canvas not yet rendered, use default size
                canvas_width, canvas_height = 500, 400
            
            # Calculate scaling to fit image in canvas
            img_width, img_height = self.current_image.size
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            scale = min(scale_x, scale_y, 1.0)  # Don't scale up
            
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            self.current_image = self.current_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(self.current_image)
            
            # Clear canvas and display image
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width//2, canvas_height//2, image=self.current_photo, anchor="center")
            
            # Clear selection and straightening
            self.selection_start = None
            self.selection_end = None
            self.selection_rect = None
            self.straightening_points = []
            self.straightening_lines = []
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")
    
    def toggle_straightening_mode(self):
        """Toggle straightening mode on/off"""
        self.straightening_mode = not self.straightening_mode
        
        if self.straightening_mode:
            self.straighten_btn.configure(text="Exit Straighten", fg_color="red", hover_color="darkred")
            self.instructions_label.configure(text="Click two points to define a line to straighten")
            # Clear any existing straightening points
            self.straightening_points = []
            self.straightening_lines = []
        else:
            self.straighten_btn.configure(text="Straighten Image", fg_color="orange", hover_color="darkorange")
            self.instructions_label.configure(text="Click and drag to select text area for OCR")
            # Clear straightening visual elements
            for line in self.straightening_lines:
                self.canvas.delete(line)
            self.straightening_lines = []
    
    def on_canvas_click(self, event):
        """Handle canvas click events for both selection and straightening"""
        if self.straightening_mode:
            self.handle_straightening_click(event)
        else:
            self.start_selection(event)
    
    def handle_straightening_click(self, event):
        """Handle clicks in straightening mode"""
        if len(self.straightening_points) < 2:
            # Add point
            self.straightening_points.append((event.x, event.y))
            
            # Draw a small circle at the click point
            circle = self.canvas.create_oval(
                event.x - 3, event.y - 3,
                event.x + 3, event.y + 3,
                fill="red", outline="red"
            )
            self.straightening_lines.append(circle)
            
            if len(self.straightening_points) == 2:
                # Draw line between the two points
                line = self.canvas.create_line(
                    self.straightening_points[0][0], self.straightening_points[0][1],
                    self.straightening_points[1][0], self.straightening_points[1][1],
                    fill="red", width=2
                )
                self.straightening_lines.append(line)
                
                # Perform straightening
                self.straighten_image()
                
                # Reset for next straightening operation
                self.straightening_points = []
                for line in self.straightening_lines:
                    self.canvas.delete(line)
                self.straightening_lines = []
    
    def straighten_image(self):
        """Straighten the image based on the two selected points"""
        if len(self.straightening_points) != 2:
            return
        
        try:
            # Calculate angle between the line and horizontal
            x1, y1 = self.straightening_points[0]
            x2, y2 = self.straightening_points[1]
            
            # Calculate angle in degrees
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            
            # Rotate the original image
            rotated_image = self.original_image.rotate(-angle, expand=True, fillcolor='white')
            
            # Update current image
            self.current_image = rotated_image
            
            # Resize to fit canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
                canvas_width, canvas_height = 500, 400
            
            img_width, img_height = self.current_image.size
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            scale = min(scale_x, scale_y, 1.0)
            
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            self.current_image = self.current_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(self.current_image)
            
            # Update canvas
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width//2, canvas_height//2, image=self.current_photo, anchor="center")
            
            # Exit straightening mode
            self.toggle_straightening_mode()
            
            messagebox.showinfo("Success", f"Image straightened by {angle:.1f} degrees")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to straighten image: {str(e)}")
    
    def start_selection(self, event):
        """Start drawing selection rectangle"""
        self.selection_start = (event.x, event.y)
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
    
    def update_selection(self, event):
        """Update selection rectangle while dragging"""
        if self.selection_start and not self.straightening_mode:
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
            self.selection_rect = self.canvas.create_rectangle(
                self.selection_start[0], self.selection_start[1],
                event.x, event.y,
                outline="red", width=2
            )
    
    def end_selection(self, event):
        """End selection rectangle drawing"""
        if self.selection_start and not self.straightening_mode:
            self.selection_end = (event.x, event.y)
    
    def run_ocr_on_selection(self):
        """Run OCR on the selected area of the image"""
        if not self.current_image or not self.selection_start or not self.selection_end:
            messagebox.showwarning("Warning", "Please select an area on the image first")
            return
        
        try:
            # Get selection coordinates
            x1, y1 = self.selection_start
            x2, y2 = self.selection_end
            
            # Ensure coordinates are in correct order
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            
            # Convert canvas coordinates to image coordinates
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Calculate image position on canvas
            img_width, img_height = self.current_image.size
            img_x = (canvas_width - img_width) // 2
            img_y = (canvas_height - img_height) // 2
            
            # Convert to image coordinates
            img_x1 = max(0, x1 - img_x)
            img_y1 = max(0, y1 - img_y)
            img_x2 = min(img_width, x2 - img_x)
            img_y2 = min(img_height, y2 - img_y)
            
            # Crop the image
            cropped_image = self.current_image.crop((img_x1, img_y1, img_x2, img_y2))
            
            # Run OCR
            ocr_text = pytesseract.image_to_string(cropped_image, lang='eng')
            
            # Display results
            self.ocr_textbox.configure(state="normal")
            self.ocr_textbox.delete("1.0", "end")
            self.ocr_textbox.insert("1.0", ocr_text.strip())
            self.ocr_textbox.configure(state="disabled")
            
        except Exception as e:
            messagebox.showerror("Error", f"OCR failed: {str(e)}")
    
    def previous_image(self):
        """Navigate to the previous image"""
        if self.image_files and self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_current_image()
            self.update_status()
            self.populate_image_navigator()
            self.clear_form()
    
    def next_image(self):
        """Navigate to the next image"""
        if self.image_files and self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.load_current_image()
            self.update_status()
            self.populate_image_navigator()
            self.clear_form()
    
    def clear_form(self):
        """Clear all form fields"""
        self.plot_entry.delete(0, "end")
        self.epitaph_textbox.delete("1.0", "end")
        self.ocr_textbox.configure(state="normal")
        self.ocr_textbox.delete("1.0", "end")
        self.ocr_textbox.configure(state="disabled")
        
        # Clear all person frames
        for person_frame in self.person_frames:
            person_frame.clear_data()
    
    def save_to_backend(self):
        """Save records to backend database"""
        if not self.backend_connected:
            messagebox.showerror("Error", "Backend not connected")
            return
        
        if not self.current_cemetery:
            messagebox.showerror("Error", "No cemetery selected")
            return
        
        if not self.image_files:
            messagebox.showwarning("Warning", "No images loaded")
            return
        
        # Get current image filename
        current_file = self.image_files[self.current_image_index]
        filename = current_file.name
        
        # Get common data
        plot_location = self.plot_entry.get().strip()
        epitaph = self.epitaph_textbox.get("1.0", "end").strip()
        ocr_text = self.ocr_textbox.get("1.0", "end").strip()
        
        # Validate that we have at least one person with a name
        valid_persons = []
        for person_frame in self.person_frames:
            person_data = person_frame.get_data()
            if person_data['name']:  # Only save if name is provided
                valid_persons.append(person_data)
        
        if not valid_persons:
            messagebox.showwarning("Warning", "Please enter at least one person's name")
            return
        
        try:
            # Create plot in backend
            plot = self.api.create_plot(
                self.current_cemetery['id'],
                plot_location or filename,
                latitude=None,  # Could be extracted from GPS data
                longitude=None
            )
            
            if not plot:
                messagebox.showerror("Error", "Failed to create plot in backend")
                return
            
            plot_id = plot['id']
            
            # Upload photo
            photo_result = self.api.upload_photo(plot_id, str(current_file), "headstone")
            if photo_result:
                print(f"Uploaded photo: {filename}")
            
            # Add individuals
            records_saved = 0
            for person_data in valid_persons:
                individual = self.api.add_individual(
                    plot_id,
                    person_data['name'],
                    person_data['born'] if person_data['born'] else None,
                    person_data['died'] if person_data['died'] else None,
                    epitaph,
                    "primary" if records_saved == 0 else "family"
                )
                
                if individual:
                    records_saved += 1
                    print(f"Added individual: {person_data['name']}")
            
            # Show confirmation
            messagebox.showinfo("Success", f"Saved {records_saved} record(s) to backend for {filename}")
            
            # Clear form for next entry
            self.clear_form()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save to backend: {str(e)}")
    
    def save_records(self):
        """Save records locally (fallback method)"""
        if not self.image_files:
            messagebox.showwarning("Warning", "No images loaded")
            return
        
        # Get current image filename
        current_file = self.image_files[self.current_image_index]
        filename = current_file.name
        
        # Get common data
        plot_location = self.plot_entry.get().strip()
        epitaph = self.epitaph_textbox.get("1.0", "end").strip()
        ocr_text = self.ocr_textbox.get("1.0", "end").strip()
        
        # Validate that we have at least one person with a name
        valid_persons = []
        for person_frame in self.person_frames:
            person_data = person_frame.get_data()
            if person_data['name']:  # Only save if name is provided
                valid_persons.append(person_data)
        
        if not valid_persons:
            messagebox.showwarning("Warning", "Please enter at least one person's name")
            return
        
        # Save a record for each valid person
        records_saved = 0
        for person_data in valid_persons:
            record = {
                'image_filename': filename,
                'plot_location': plot_location,
                'name': person_data['name'],
                'born': person_data['born'],
                'died': person_data['died'],
                'epitaph': epitaph,
                'ocr_text': ocr_text
            }
            self.data_records.append(record)
            records_saved += 1
        
        # Show confirmation
        messagebox.showinfo("Success", f"Saved {records_saved} record(s) locally for {filename}")
        
        # Clear form for next entry
        self.clear_form()
    
    def update_status(self):
        """Update the status label"""
        if self.image_files:
            status_text = f"Viewing image {self.current_image_index + 1} of {len(self.image_files)}"
            if self.image_files:
                filename = self.image_files[self.current_image_index].name
                status_text += f"\n{filename}"
        else:
            status_text = "No images loaded"
        
        self.status_label.configure(text=status_text)
    
    def save_data_to_csv(self):
        """Save all records to CSV file"""
        if self.data_records:
            try:
                df = pd.DataFrame(self.data_records, columns=self.data_columns)
                df.to_csv('database_final.csv', index=False)
                print(f"Saved {len(self.data_records)} records to database_final.csv")
            except Exception as e:
                print(f"Error saving CSV: {str(e)}")
        else:
            print("No records to save")
    
    def on_closing(self):
        """Handle application closing"""
        self.save_data_to_csv()
        self.root.destroy()
    
    def run(self):
        """Start the application"""
        self.root.mainloop()

def main():
    """Main function to run the application"""
    try:
        app = ElysianScribe()
        app.run()
    except Exception as e:
        print(f"Application error: {str(e)}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {str(e)}")

if __name__ == "__main__":
    main()
