#!/bin/bash

# LinkedIn Job Scraper - Google Cloud Run Deploy Script
# Bu script uygulamayı Google Cloud Run'a deploy eder

set -e  # Hata durumunda scripti durdur

echo "================================================"
echo "LinkedIn Job Scraper - Cloud Run Deployment"
echo "================================================"

# Renkler
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Yapılandırma
PROJECT_ID=${GCP_PROJECT_ID:-""}
SERVICE_NAME=${SERVICE_NAME:-"linkedin-job-scraper"}
REGION=${REGION:-"us-central1"}
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Project ID kontrolü
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}[HATA]${NC} GCP_PROJECT_ID environment variable tanımlı değil!"
    echo ""
    echo "Kullanım:"
    echo "  export GCP_PROJECT_ID='your-project-id'"
    echo "  ./deploy-cloudrun.sh"
    echo ""
    echo "veya:"
    echo "  GCP_PROJECT_ID='your-project-id' ./deploy-cloudrun.sh"
    exit 1
fi

echo -e "${BLUE}[INFO]${NC} Project ID: ${PROJECT_ID}"
echo -e "${BLUE}[INFO]${NC} Service Name: ${SERVICE_NAME}"
echo -e "${BLUE}[INFO]${NC} Region: ${REGION}"
echo -e "${BLUE}[INFO]${NC} Image: ${IMAGE_NAME}"
echo ""

# 1. Google Cloud SDK kontrolü
echo -e "${YELLOW}[1/5]${NC} Google Cloud SDK kontrol ediliyor..."
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}[HATA]${NC} gcloud CLI bulunamadı!"
    echo "Google Cloud SDK'yı yükleyin: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
echo -e "${GREEN}✓${NC} gcloud CLI bulundu"

# 2. Docker kontrolü
echo -e "${YELLOW}[2/5]${NC} Docker kontrol ediliyor..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[HATA]${NC} Docker bulunamadı!"
    echo "Docker'ı yükleyin: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker bulundu"

# 3. GCP Authentication
echo -e "${YELLOW}[3/5]${NC} GCP Authentication kontrol ediliyor..."
gcloud config set project ${PROJECT_ID}
gcloud auth configure-docker --quiet

# 4. Docker Image Build
echo -e "${YELLOW}[4/5]${NC} Docker image build ediliyor..."
echo -e "${BLUE}[INFO]${NC} Bu işlem birkaç dakika sürebilir..."
docker build -t ${IMAGE_NAME} .

# Docker image'ı push et
echo -e "${YELLOW}[4/5]${NC} Docker image GCR'ye push ediliyor..."
docker push ${IMAGE_NAME}

echo -e "${GREEN}✓${NC} Docker image başarıyla push edildi"

# 5. Cloud Run'a Deploy
echo -e "${YELLOW}[5/5]${NC} Cloud Run'a deploy ediliyor..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --concurrency 80 \
    --max-instances 10 \
    --set-env-vars "SELENIUM_HEADLESS=True" \
    --set-env-vars "MAX_PAGES_LIMIT=10" \
    --set-env-vars "MAX_CONCURRENT_JOBS=2"

echo ""
echo "================================================"
echo -e "${GREEN}✓ DEPLOYMENT BAŞARILI!${NC}"
echo "================================================"
echo ""

# Service URL'ini al
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')

echo -e "${GREEN}Uygulama URL:${NC} ${SERVICE_URL}"
echo ""
echo -e "${YELLOW}Önemli Notlar:${NC}"
echo "- Selenium kullandığı için Cloud Run'da daha fazla memory/CPU gerekir"
echo "- Timeout süresi 3600 saniye (1 saat) olarak ayarlandı"
echo "- Her arama işlemi için en fazla 10 sayfa tarayın (Cloud Run limitleri)"
echo "- Concurrent job sayısı 2 ile sınırlandırıldı"
echo ""
echo -e "${BLUE}Monitoring:${NC}"
echo "  gcloud run services logs read ${SERVICE_NAME} --region ${REGION} --limit 50"
echo ""
