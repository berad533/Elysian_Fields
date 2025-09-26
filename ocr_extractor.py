"""
OCR Text Extractor for Project Elysian Fields
Extracts text from images using Tesseract OCR and saves results to CSV

Dependencies:
- pytesseract
- pandas
- Pillow (PIL)
- tesseract-ocr (system installation required)

Author: Project Elysian Fields Development Team
"""

import os
import pandas as pd
from PIL import Image
import pytesseract
import re
from pathlib import Path

# TESSERACT CONFIGURATION
# IMPORTANT: Verify this path is correct for your Tesseract installation
# Common Windows paths:
# - C:\Program Files\Tesseract-OCR\tesseract.exe
# - C:\Program Files (x86)\Tesseract-OCR\tesseract.exe
# For other systems, check: which tesseract (Linux/Mac)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def setup_directories():
    """
    Set up the required directories and check for images folder
    """
    script_dir = Path(__file__).parent
    images_dir = script_dir / 'images'
    output_file = script_dir / 'database.csv'
    
    # Check if images directory exists
    if not images_dir.exists():
        print(f"Error: Images directory not found at {images_dir}")
        print("Please create an 'images' folder in the same directory as this script.")
        return None, None
    
    # Check if images directory is empty
    image_files = list(images_dir.glob('*'))
    if not image_files:
        print(f"Warning: No files found in {images_dir}")
        return images_dir, output_file
    
    print(f"Found {len(image_files)} files in images directory")
    return images_dir, output_file

def is_image_file(file_path):
    """
    Check if a file is a supported image format
    """
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif'}
    return file_path.suffix.lower() in supported_extensions

def extract_text_from_image(image_path):
    """
    Extract text from an image using Tesseract OCR
    
    Args:
        image_path (Path): Path to the image file
        
    Returns:
        str: Extracted text from the image
    """
    try:
        # Open the image using PIL
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for PNG with transparency, etc.)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Extract text using pytesseract
            # Using default language (English) - can be modified if needed
            extracted_text = pytesseract.image_to_string(img, lang='eng')
            
            # Clean up the text (remove excessive whitespace)
            cleaned_text = re.sub(r'\s+', ' ', extracted_text.strip())
            
            return cleaned_text
            
    except Exception as e:
        print(f"Error processing {image_path.name}: {str(e)}")
        return f"ERROR: Could not process image - {str(e)}"

def parse_extracted_text(text):
    """
    Attempt to parse extracted text for structured data
    This is a basic implementation - can be enhanced based on specific needs
    
    Args:
        text (str): Raw extracted text
        
    Returns:
        dict: Parsed data with common fields
    """
    parsed_data = {
        'raw_text': text,
        'potential_name': '',
        'potential_dates': [],
        'word_count': len(text.split()) if text else 0
    }
    
    # Look for potential names (capitalized words, 2-3 words)
    name_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b'
    names = re.findall(name_pattern, text)
    if names:
        parsed_data['potential_name'] = names[0]  # Take the first potential name
    
    # Look for dates (various formats)
    date_patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or MM-DD-YYYY
        r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',    # YYYY/MM/DD or YYYY-MM-DD
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',  # Month DD, YYYY
        r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b'  # DD Month YYYY
    ]
    
    dates = []
    for pattern in date_patterns:
        dates.extend(re.findall(pattern, text, re.IGNORECASE))
    
    parsed_data['potential_dates'] = dates
    
    return parsed_data

def process_images(images_dir):
    """
    Process all images in the directory and extract text
    
    Args:
        images_dir (Path): Path to the images directory
        
    Returns:
        list: List of dictionaries containing extracted data
    """
    extracted_data = []
    
    # Get all files in the images directory
    all_files = list(images_dir.iterdir())
    image_files = [f for f in all_files if f.is_file() and is_image_file(f)]
    
    if not image_files:
        print("No supported image files found in the images directory")
        return extracted_data
    
    print(f"Processing {len(image_files)} image files...")
    
    for i, image_path in enumerate(image_files, 1):
        print(f"Processing {i}/{len(image_files)}: {image_path.name}")
        
        # Extract text from the image
        extracted_text = extract_text_from_image(image_path)
        
        # Parse the extracted text for additional insights
        parsed_data = parse_extracted_text(extracted_text)
        
        # Create record for CSV
        record = {
            'image_filename': image_path.name,
            'extracted_text': extracted_text,
            'potential_name': parsed_data['potential_name'],
            'potential_dates': '; '.join(parsed_data['potential_dates']) if parsed_data['potential_dates'] else '',
            'word_count': parsed_data['word_count'],
            'file_size_bytes': image_path.stat().st_size,
            'file_extension': image_path.suffix.lower()
        }
        
        extracted_data.append(record)
    
    return extracted_data

def save_to_csv(data, output_file):
    """
    Save the extracted data to a CSV file
    
    Args:
        data (list): List of dictionaries containing extracted data
        output_file (Path): Path where the CSV file should be saved
    """
    if not data:
        print("No data to save to CSV")
        return
    
    try:
        # Create DataFrame from the data
        df = pd.DataFrame(data)
        
        # Save to CSV without index
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"Data successfully saved to {output_file}")
        print(f"CSV contains {len(data)} records with columns: {list(df.columns)}")
        
    except Exception as e:
        print(f"Error saving CSV file: {str(e)}")

def main():
    """
    Main function to orchestrate the OCR extraction process
    """
    print("=" * 60)
    print("Project Elysian Fields - OCR Text Extractor")
    print("=" * 60)
    
    # Setup directories
    images_dir, output_file = setup_directories()
    if images_dir is None:
        return
    
    # Process images and extract text
    extracted_data = process_images(images_dir)
    
    if not extracted_data:
        print("No data extracted. Please check your images and try again.")
        return
    
    # Save results to CSV
    save_to_csv(extracted_data, output_file)
    
    # Final confirmation
    print("=" * 60)
    print(f"Extraction complete. {output_file.name} has been created with {len(extracted_data)} records.")
    print("=" * 60)

if __name__ == "__main__":
    main()
