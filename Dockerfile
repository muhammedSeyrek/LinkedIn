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
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
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
