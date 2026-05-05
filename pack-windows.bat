@echo off
REM Invoice Scrapper - Windows Packaging Script
REM Builds a standalone .exe bundling Python, dependencies, and Tesseract.
REM
REM Prerequisites:
REM   - Python 3.13+ with uv installed
REM   - Tesseract OCR installed (https://github.com/UB-Mannheim/tesseract/wiki)
REM   - Portuguese language data selected during Tesseract installation
REM   - Run "uv sync --all-extras" first to install dependencies

echo === Invoice Scrapper - Windows Packaging ===
echo.

REM Check Tesseract is available
where tesseract >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Tesseract not found in PATH.
    echo Install from: https://github.com/UB-Mannheim/tesseract/wiki
    echo Ensure "Add to PATH" is selected during installation.
    exit /b 1
)

REM Find Tesseract binary
for /f "tokens=*" %%i in ('where tesseract') do set TESS_BIN=%%i
echo Found Tesseract: %TESS_BIN%

REM Find tessdata directory (check common locations)
set TESSDATA_DIR=
if exist "C:\Program Files\Tesseract-OCR\tessdata\por.traineddata" (
    set TESSDATA_DIR=C:\Program Files\Tesseract-OCR\tessdata
)
if exist "C:\Program Files (x86)\Tesseract-OCR\tessdata\por.traineddata" (
    set TESSDATA_DIR=C:\Program Files (x86)\Tesseract-OCR\tessdata
)

if "%TESSDATA_DIR%"=="" (
    echo ERROR: Portuguese language data not found.
    echo Reinstall Tesseract and select Portuguese during installation.
    exit /b 1
)
echo Found tessdata: %TESSDATA_DIR%
echo.

REM Check Portuguese data exists
if not exist "%TESSDATA_DIR%\por.traineddata" (
    echo ERROR: por.traineddata not found in %TESSDATA_DIR%
    exit /b 1
)

echo Building InvoiceScrapper.exe...
echo.

uv run flet pack main.py ^
  -n InvoiceScrapper ^
  --product-name "Invoice Scrapper" ^
  --product-version 0.1.0 ^
  --add-data "invoice_scrapper;invoice_scrapper" ^
  --add-binary "%TESS_BIN%;." ^
  --add-data "%TESSDATA_DIR%\por.traineddata;tessdata" ^
  --add-data "%TESSDATA_DIR%\eng.traineddata;tessdata" ^
  --hidden-import invoice_scrapper ^
  --hidden-import invoice_scrapper.bundle_paths ^
  --hidden-import invoice_scrapper.ui.app ^
  --hidden-import invoice_scrapper.config ^
  --hidden-import invoice_scrapper.models ^
  --hidden-import invoice_scrapper.pdf_reader ^
  --hidden-import invoice_scrapper.table_detector ^
  --hidden-import invoice_scrapper.field_extractor ^
  --hidden-import invoice_scrapper.invoice_processor ^
  --hidden-import invoice_scrapper.excel_writer ^
  --distpath dist\windows ^
  --company-name "Invoice Scrapper"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Build failed.
    exit /b 1
)

echo.
echo === Build complete ===
echo Output: dist\windows\InvoiceScrapper.exe
