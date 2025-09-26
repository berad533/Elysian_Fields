# ocr_server.py (Final Version)
# Correctly handles multipart/form-data file uploads from the React front-end.

from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import pytesseract
import io

# --- TESSERACT CONFIGURATION ---
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except Exception:
    print("Warning: Tesseract OCR engine not found at default path.")

# --- FLASK APP SETUP ---
app = Flask(__name__)
# This enables Cross-Origin Resource Sharing (CORS) for the entire app
CORS(app)

@app.route('/ocr', methods=['POST'])
def perform_ocr():
    """
    This endpoint expects an image file uploaded via multipart/form-data.
    It performs OCR on the image and returns the extracted text.
    """
    print("\n--- New Request Received ---")
    
    # Check if an image file is part of the request
    if 'image' not in request.files:
        print(">>> ERROR: 'image' key not found in request.files.")
        return jsonify({"error": "No image file found in request (key 'image' is missing)"}), 400

    file = request.files['image']

    # Check if the file is empty
    if file.filename == '':
        print(">>> ERROR: File found, but filename is empty.")
        return jsonify({"error": "No image file selected"}), 400

    if file:
        try:
            print(f">>> DEBUG: Processing file: {file.filename}")
            image_bytes = file.read()
            image = Image.open(io.BytesIO(image_bytes))

            # Perform OCR using Tesseract
            extracted_text = pytesseract.image_to_string(image)
            print(">>> DEBUG: OCR successful.")

            return jsonify({"text": extracted_text})

        except Exception as e:
            print(f">>> ERROR: An error occurred during processing: {str(e)}")
            return jsonify({"error": f"An error occurred during OCR processing: {str(e)}"}), 500

    return jsonify({"error": "An unknown error occurred"}), 500

if __name__ == '__main__':
    print("--- Elysian Scribe Local OCR Service ---")
    print("--> Listening on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000)