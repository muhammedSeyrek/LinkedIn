#!/bin/bash

# LinkedIn Job Scraper - Run Script
# Bu script uygulamayı başlatır

echo "============================================"
echo "LinkedIn İş Arama Asistanı Başlatılıyor..."
echo "============================================"

# Renk kodları
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Gerekli klasörleri oluştur
echo -e "${YELLOW}[1/4]${NC} Gerekli klasörler oluşturuluyor..."
mkdir -p logs
mkdir -p static/results
mkdir -p temp

# Virtual environment kontrolü
if [ -d ".venv" ]; then
    echo -e "${GREEN}[2/4]${NC} Virtual environment bulundu"
    # Windows için .venv/Scripts, Linux için .venv/bin
    if [ -f ".venv/Scripts/activate" ]; then
        source .venv/Scripts/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
else
    echo -e "${YELLOW}[2/4]${NC} Virtual environment oluşturuluyor..."
    python -m venv .venv
    if [ -f ".venv/Scripts/activate" ]; then
        source .venv/Scripts/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi

    echo -e "${YELLOW}[3/4]${NC} Bağımlılıklar yükleniyor..."
    pip install -r requirements.txt
fi

# .env dosyası kontrolü
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[3/4]${NC} .env dosyası bulunamadı, .env.example'dan kopyalanıyor..."
    cp .env.example .env
    echo -e "${YELLOW}→${NC} .env dosyasını düzenlemeniz önerilir"
fi

# Uygulamayı başlat
echo -e "${GREEN}[4/4]${NC} Uygulama başlatılıyor..."
echo ""
echo -e "${GREEN}✓${NC} Uygulama çalışıyor!"
echo -e "${GREEN}✓${NC} Tarayıcınızda açın: ${YELLOW}http://127.0.0.1:5000${NC}"
echo ""
echo -e "Durdurmak için ${RED}Ctrl+C${NC} tuşlarına basın"
echo "============================================"
echo ""

# Flask uygulamasını başlat
python app.py
