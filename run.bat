@echo off
REM LinkedIn Job Scraper - Windows Run Script
REM Bu script uygulamayı Windows'ta başlatır

echo ============================================
echo LinkedIn Is Arama Asistani Baslatiliyor...
echo ============================================

REM Gerekli klasörleri oluştur
echo [1/4] Gerekli klasorler olusturuluyor...
if not exist "logs" mkdir logs
if not exist "static\results" mkdir static\results
if not exist "temp" mkdir temp

REM Virtual environment kontrolü
if exist ".venv" (
    echo [2/4] Virtual environment bulundu
    call .venv\Scripts\activate.bat
) else (
    echo [2/4] Virtual environment olusturuluyor...
    python -m venv .venv
    call .venv\Scripts\activate.bat

    echo [3/4] Bagimliliklar yukleniyor...
    pip install -r requirements.txt
)

REM .env dosyası kontrolü
if not exist ".env" (
    echo [3/4] .env dosyasi bulunamadi, .env.example'dan kopyalaniyor...
    copy .env.example .env
    echo --^> .env dosyasini duzenlemeniz onerilir
)

REM Uygulamayı başlat
echo [4/4] Uygulama baslatiliyor...
echo.
echo [OK] Uygulama calisiyor!
echo [OK] Tarayicinizda acin: http://127.0.0.1:5000
echo.
echo Durdurmak icin Ctrl+C tusularina basin
echo ============================================
echo.

REM Flask uygulamasını başlat
python app.py

pause
