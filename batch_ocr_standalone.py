"""
Standalone Batch OCR Script
Automatically processes all images in a folder and creates a database
"""

import os
import sys
import pandas as pd
import pytesseract
from PIL import Image
import re
from pathlib import Path
import argparse

class BatchOCRProcessor:
    def __init__(self, tesseract_path=None):
        """Initialize the batch OCR processor"""
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        else:
            # Try default path
            default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        
        self.results = []
    
    def process_folder(self, folder_path, output_csv=None):
        """Process all images in a folder"""
        print(f"🔍 Processing folder: {folder_path}")
        print("=" * 50)
        
        # Get all image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        image_files = []
        
        for file in os.listdir(folder_path):
            if Path(file).suffix.lower() in image_extensions:
                image_files.append(os.path.join(folder_path, file))
        
        if not image_files:
            print("❌ No image files found in the folder")
            return
        
        print(f"📸 Found {len(image_files)} image files")
        print("-" * 30)
        
        # Process each image
        successful = 0
        failed = 0
        
        for i, image_path in enumerate(image_files, 1):
            print(f"Processing {i}/{len(image_files)}: {os.path.basename(image_path)}")
            
            try:
                result = self.process_single_image(image_path)
                if result:
                    self.results.append(result)
                    successful += 1
                    print(f"  ✅ Extracted: {result['name']}")
                else:
                    failed += 1
                    print(f"  ❌ No text extracted")
            except Exception as e:
                failed += 1
                print(f"  ❌ Error: {e}")
        
        # Save results
        if self.results:
            if output_csv:
                csv_path = output_csv
            else:
                csv_path = os.path.join(folder_path, "batch_ocr_results.csv")
            
            self.save_results(csv_path)
            print(f"\n✅ Results saved to: {csv_path}")
        
        print(f"\n📊 Summary:")
        print(f"  ✅ Successful: {successful}")
        print(f"  ❌ Failed: {failed}")
        print(f"  📄 Total records: {len(self.results)}")
    
    def process_single_image(self, image_path):
        """Process a single image with OCR"""
        try:
            # Load image
            image = Image.open(image_path)
            
            # Run OCR
            extracted_text = pytesseract.image_to_string(image)
            
            if not extracted_text.strip():
                return None
            
            # Parse the text
            parsed_data = self.parse_ocr_text(extracted_text)
            
            return {
                'image_filename': os.path.basename(image_path),
                'image_path': image_path,
                'extracted_text': extracted_text,
                'name': parsed_data['name'],
                'born_date': parsed_data['born_date'],
                'died_date': parsed_data['died_date'],
                'epitaph': parsed_data['epitaph']
            }
            
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return None
    
    def parse_ocr_text(self, text):
        """Parse OCR text to extract structured data"""
        # Clean up text
        text = text.strip()
        
        # Split into lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Extract name (usually first line)
        name = lines[0] if lines else 'Unknown'
        
        # Extract dates
        date_pattern = r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})\b'
        dates = re.findall(date_pattern, text)
        
        born_date = None
        died_date = None
        
        if len(dates) >= 2:
            # First date is birth, second is death
            born_date = dates[0]
            died_date = dates[1]
        elif len(dates) == 1:
            # Only one date, assume death date
            died_date = dates[0]
        
        # Extract epitaph (remaining text)
        epitaph = ''
        if len(lines) > 2:
            epitaph = ' '.join(lines[2:])
        
        return {
            'name': name,
            'born_date': born_date,
            'died_date': died_date,
            'epitaph': epitaph
        }
    
    def save_results(self, csv_path):
        """Save results to CSV file"""
        if not self.results:
            return
        
        df = pd.DataFrame(self.results)
        df.to_csv(csv_path, index=False)
        print(f"💾 Saved {len(self.results)} records to CSV")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Batch OCR Processing for Gravestone Images')
    parser.add_argument('folder', help='Folder containing gravestone images')
    parser.add_argument('--output', '-o', help='Output CSV file path')
    parser.add_argument('--tesseract', '-t', help='Path to Tesseract executable')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.folder):
        print(f"❌ Folder not found: {args.folder}")
        return 1
    
    # Initialize processor
    processor = BatchOCRProcessor(args.tesseract)
    
    # Process folder
    processor.process_folder(args.folder, args.output)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
