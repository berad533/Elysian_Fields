@echo off
echo Batch OCR Processing for Gravestone Images
echo ==========================================
echo.
set /p folder="Enter folder path containing images: "
echo.
echo Processing images in: %folder%
echo.
python batch_ocr_standalone.py "%folder%"
echo.
pause
