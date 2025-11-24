# Google Cloud Run Deployment Guide

Bu dokümanda LinkedIn Job Scraper uygulamasının Google Cloud Run'a nasıl deploy edileceği anlatılmaktadır.

## 📋 Ön Gereksinimler

### 1. Google Cloud Hesabı
- [Google Cloud Console](https://console.cloud.google.com/) hesabı
- Aktif bir GCP projesi
- Billing etkin olmalı

### 2. Gerekli Araçlar
```bash
# Google Cloud SDK
# https://cloud.google.com/sdk/docs/install

# Docker Desktop
# https://docs.docker.com/get-docker/

# Git
# https://git-scm.com/downloads
```

### 3. GCP API'lerini Etkinleştirme
```bash
# Cloud Run API
gcloud services enable run.googleapis.com

# Container Registry API
gcloud services enable containerregistry.googleapis.com

# Cloud Build API (opsiyonel, otomatik build için)
gcloud services enable cloudbuild.googleapis.com
```

## 🚀 Hızlı Deploy

### Yöntem 1: Otomatik Script (Önerilen)

```bash
# 1. Proje ID'nizi ayarlayın
export GCP_PROJECT_ID="your-project-id"

# 2. Deploy scriptini çalıştırın
chmod +x deploy-cloudrun.sh
./deploy-cloudrun.sh
```

### Yöntem 2: Manuel Deploy

#### Adım 1: Docker Image Build
```bash
# Project ID'nizi ayarlayın
export PROJECT_ID="your-project-id"

# Docker image build edin
docker build -t gcr.io/${PROJECT_ID}/linkedin-job-scraper .
```

#### Adım 2: Image'ı GCR'ye Push Edin
```bash
# Docker'ı GCR ile yapılandırın
gcloud auth configure-docker

# Image'ı push edin
docker push gcr.io/${PROJECT_ID}/linkedin-job-scraper
```

#### Adım 3: Cloud Run'a Deploy Edin
```bash
gcloud run deploy linkedin-job-scraper \
    --image gcr.io/${PROJECT_ID}/linkedin-job-scraper \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --max-instances 10
```

## ⚙️ Yapılandırma

### Environment Variables

Cloud Run deployment sırasında environment variables ayarlayabilirsiniz:

```bash
--set-env-vars "SELENIUM_HEADLESS=True,MAX_PAGES_LIMIT=10,MAX_CONCURRENT_JOBS=2"
```

### Önemli Ayarlar

| Ayar | Değer | Açıklama |
|------|-------|----------|
| **Memory** | 2Gi | Selenium için minimum 2GB RAM gerekli |
| **CPU** | 2 | 2 vCPU önerilir |
| **Timeout** | 3600s | Maksimum 1 saat (Cloud Run limiti) |
| **Concurrency** | 80 | Aynı anda işlenebilecek istek sayısı |
| **Max Instances** | 10 | Otomatik scaling limiti |

## 🔧 Cloud Run için Özel Ayarlamalar

### 1. Selenium Chrome Ayarları

Dockerfile'da Chrome ve ChromeDriver otomatik olarak yüklenir:
- **Headless Mode**: Zorunlu (GUI yok)
- **No Sandbox**: Cloud Run için gerekli
- **Disable Dev Shm**: Memory optimizasyonu

### 2. Dosya Sistemi Limitleri

Cloud Run stateless'tır ve disk yazma limitleri vardır:
- **CSV Sonuçları**: `/tmp` veya Cloud Storage kullanın
- **Log Dosyaları**: Cloud Logging'e yönlendirilir
- **Geçici Dosyalar**: Container restart'ında silinir

### 3. Timeout Yönetimi

```python
# app.py içinde
MAX_PAGES_LIMIT = int(os.environ.get('MAX_PAGES_LIMIT', '10'))
JOB_TIMEOUT_MINUTES = int(os.environ.get('JOB_TIMEOUT_MINUTES', '50'))
```

Cloud Run default timeout 5 dakikadır, maksimum 60 dakika ayarlanabilir.

## 📊 Monitoring ve Logging

### Log'ları Görüntüleme

```bash
# Real-time logs
gcloud run services logs tail linkedin-job-scraper --region us-central1

# Son 50 satır
gcloud run services logs read linkedin-job-scraper --region us-central1 --limit 50

# Hata logları
gcloud run services logs read linkedin-job-scraper --region us-central1 --log-filter "severity>=ERROR"
```

### Cloud Console'dan İzleme

1. [Cloud Run Console](https://console.cloud.google.com/run)
2. Servisinizi seçin
3. **LOGS**, **METRICS**, **REVISIONS** sekmelerini inceleyin

## 💰 Maliyet Optimizasyonu

### Free Tier
Cloud Run ücretsiz kullanım kotası:
- 2 million istekler/ay
- 360,000 GB-seconds
- 180,000 vCPU-seconds
- 1 GB network egress

### Maliyet Azaltma İpuçları

1. **Min Instances = 0**: Kullanılmadığında ücret ödemeyin
2. **Max Pages Limit = 5-10**: Daha az kaynak kullanımı
3. **Max Concurrent Jobs = 2**: Aynı anda az iş çalıştırın
4. **Timeout Düşürün**: Gerekmedikçe 3600s kullanmayın

```bash
# Maliyet optimize edilmiş deploy
gcloud run deploy linkedin-job-scraper \
    --image gcr.io/${PROJECT_ID}/linkedin-job-scraper \
    --memory 1Gi \
    --cpu 1 \
    --timeout 1800 \
    --max-instances 3 \
    --min-instances 0
```

## 🔒 Güvenlik

### Authentication Ekleme

Public erişim yerine authentication kullanın:

```bash
# Authentication gerektirecek şekilde deploy
gcloud run deploy linkedin-job-scraper \
    --image gcr.io/${PROJECT_ID}/linkedin-job-scraper \
    --no-allow-unauthenticated
```

Erişim için:
```bash
# Token alın
gcloud auth print-identity-token

# Request yapın
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
     https://linkedin-job-scraper-xxx.run.app
```

### Environment Variables

Hassas bilgileri Secret Manager'da saklayın:

```bash
# Secret oluştur
echo -n "your-secret-value" | gcloud secrets create linkedin-secret --data-file=-

# Cloud Run'da kullan
gcloud run deploy linkedin-job-scraper \
    --set-secrets="SECRET_KEY=linkedin-secret:latest"
```

## 🐛 Sorun Giderme

### Problem 1: Memory Limit Aşımı
```
Error: Memory limit exceeded
```

**Çözüm:**
```bash
gcloud run services update linkedin-job-scraper \
    --memory 4Gi \
    --region us-central1
```

### Problem 2: Timeout
```
Error: Request timeout
```

**Çözüm:**
```bash
gcloud run services update linkedin-job-scraper \
    --timeout 3600 \
    --region us-central1
```

### Problem 3: Chrome Crash
```
Error: Chrome crashed
```

**Çözüm:**
- `--no-sandbox` flag kullanıldığından emin olun
- Memory'yi artırın (min 2Gi)
- CPU'yu artırın (min 2 vCPU)

### Problem 4: Build Hatası
```
ERROR: failed to build: failed to fetch ...
```

**Çözüm:**
```bash
# Docker cache temizle
docker system prune -a

# Tekrar build et
docker build --no-cache -t gcr.io/${PROJECT_ID}/linkedin-job-scraper .
```

## 📈 Performans İyileştirme

### 1. Cold Start Azaltma

```bash
# Minimum instances ayarla (ücretli)
gcloud run services update linkedin-job-scraper \
    --min-instances 1
```

### 2. Concurrency Artırma

```bash
# Daha fazla concurrent request
gcloud run services update linkedin-job-scraper \
    --concurrency 100
```

### 3. CPU Her Zaman Açık

```bash
# CPU her zaman açık (ücretli ama daha hızlı)
gcloud run services update linkedin-job-scraper \
    --cpu-always-allocated
```

## 🔄 Güncelleme ve Rollback

### Yeni Versiyon Deploy

```bash
# Yeni image build ve deploy
./deploy-cloudrun.sh
```

### Önceki Versiyona Rollback

```bash
# Revisions listele
gcloud run revisions list --service linkedin-job-scraper --region us-central1

# Belirli bir revision'a dön
gcloud run services update-traffic linkedin-job-scraper \
    --to-revisions REVISION-NAME=100 \
    --region us-central1
```

## 📚 Ek Kaynaklar

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Selenium in Docker](https://github.com/SeleniumHQ/docker-selenium)
- [Best Practices for Running Selenium on Cloud Run](https://cloud.google.com/run/docs/tips/general)

## 💡 İpuçları

1. **Test Önce Lokal**: Docker container'ı önce lokal test edin
   ```bash
   docker build -t linkedin-scraper-test .
   docker run -p 8080:8080 -e PORT=8080 linkedin-scraper-test
   ```

2. **Cloud Storage Kullanın**: Büyük CSV dosyaları için
3. **Cloud Scheduler**: Periyodik job'lar için
4. **Cloud Pub/Sub**: Asenkron işleme için
5. **Load Testing**: Deploy sonrası yük testi yapın

## 🆘 Destek

Sorun yaşıyorsanız:
- GitHub Issues: [muhammedSeyrek/LinkedIn](https://github.com/muhammedSeyrek/LinkedIn/issues)
- Email: muhammedseyrek00@gmail.com
