@echo off
setlocal
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

REM Find Tesseract binary
set "TESS_BIN="
for /f "tokens=*" %%i in ('where tesseract.exe 2^>nul') do (
    set "TESS_BIN=%%i"
    goto :tesseract_found
)

if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" (
    set "TESS_BIN=%ProgramFiles%\Tesseract-OCR\tesseract.exe"
    goto :tesseract_found
)

if defined ProgramFiles(x86) if exist "%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe" (
    set "TESS_BIN=%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe"
    goto :tesseract_found
)

if exist "%LocalAppData%\Programs\Tesseract-OCR\tesseract.exe" (
    set "TESS_BIN=%LocalAppData%\Programs\Tesseract-OCR\tesseract.exe"
    goto :tesseract_found
)

echo ERROR: Tesseract not found.
echo Install from: https://github.com/UB-Mannheim/tesseract/wiki
echo The script checks PATH, %%ProgramFiles%%\Tesseract-OCR, %%ProgramFiles(x86)%%\Tesseract-OCR,
echo and %%LocalAppData%%\Programs\Tesseract-OCR.
exit /b 1

:tesseract_found
echo Found Tesseract: %TESS_BIN%

REM Find tessdata directory (check common locations)
set "TESSDATA_DIR="
if defined TESSDATA_PREFIX if exist "%TESSDATA_PREFIX%\por.traineddata" (
    set "TESSDATA_DIR=%TESSDATA_PREFIX%"
)
if "%TESSDATA_DIR%"=="" for %%i in ("%TESS_BIN%") do if exist "%%~dpi\tessdata\por.traineddata" (
    set "TESSDATA_DIR=%%~dpi\tessdata"
)
if "%TESSDATA_DIR%"=="" if exist "%ProgramFiles%\Tesseract-OCR\tessdata\por.traineddata" (
    set "TESSDATA_DIR=%ProgramFiles%\Tesseract-OCR\tessdata"
)
if "%TESSDATA_DIR%"=="" if defined ProgramFiles(x86) if exist "%ProgramFiles(x86)%\Tesseract-OCR\tessdata\por.traineddata" (
    set "TESSDATA_DIR=%ProgramFiles(x86)%\Tesseract-OCR\tessdata"
)
if "%TESSDATA_DIR%"=="" if exist "%LocalAppData%\Programs\Tesseract-OCR\tessdata\por.traineddata" (
    set "TESSDATA_DIR=%LocalAppData%\Programs\Tesseract-OCR\tessdata"
)

if "%TESSDATA_DIR%"=="" (
    echo ERROR: Portuguese language data not found.
    echo Reinstall Tesseract and select Portuguese during installation,
    echo or set TESSDATA_PREFIX to the tessdata directory.
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

if exist "%TESSDATA_DIR%\eng.traineddata" (
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
) else (
    uv run flet pack main.py ^
      -n InvoiceScrapper ^
      --product-name "Invoice Scrapper" ^
      --product-version 0.1.0 ^
      --add-data "invoice_scrapper;invoice_scrapper" ^
      --add-binary "%TESS_BIN%;." ^
      --add-data "%TESSDATA_DIR%\por.traineddata;tessdata" ^
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
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Build failed.
    exit /b 1
)

echo.
echo === Build complete ===
echo Output: dist\windows\InvoiceScrapper.exe
