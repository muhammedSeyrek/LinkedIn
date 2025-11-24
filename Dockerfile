# LinkedIn Job Scraper - Google Cloud Run için Dockerfile
FROM python:3.11-slim

# Çalışma dizini
WORKDIR /app

# Sistem bağımlılıklarını yükle (Chrome ve dependencies)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Chrome driver için environment variables
ENV CHROME_BIN=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# Python bağımlılıklarını kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Gerekli klasörleri oluştur
RUN mkdir -p logs static/results temp && \
    chmod -R 777 logs static/results temp

# Cloud Run için port (Cloud Run PORT environment variable'ını kullanır)
ENV PORT=8080
ENV FLASK_APP=app.py
ENV SELENIUM_HEADLESS=True
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

# Non-root user oluştur (güvenlik için)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Cloud Run otomatik olarak PORT environment variable'ı atar
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 0 app:app
