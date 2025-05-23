import os
from datetime import timedelta

class Config:
    """Uygulama yapılandırma ayarları"""
    
    # Flask Ayarları
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Selenium Ayarları
    SELENIUM_HEADLESS = os.environ.get('SELENIUM_HEADLESS', 'True').lower() == 'true'
    SELENIUM_TIMEOUT = int(os.environ.get('SELENIUM_TIMEOUT', '15'))
    SELENIUM_IMPLICIT_WAIT = int(os.environ.get('SELENIUM_IMPLICIT_WAIT', '10'))
    
    # LinkedIn Scraping Ayarları
    MAX_PAGES_LIMIT = int(os.environ.get('MAX_PAGES_LIMIT', '20'))
    DEFAULT_MAX_PAGES = int(os.environ.get('DEFAULT_MAX_PAGES', '5'))
    DELAY_BETWEEN_REQUESTS = float(os.environ.get('DELAY_BETWEEN_REQUESTS', '2.0'))
    
    # Dosya Ayarları
    RESULTS_FOLDER = os.path.join('static', 'results')
    MAX_FILE_AGE_DAYS = int(os.environ.get('MAX_FILE_AGE_DAYS', '30'))
    
    # İş Yönetimi Ayarları
    MAX_CONCURRENT_JOBS = int(os.environ.get('MAX_CONCURRENT_JOBS', '3'))
    JOB_TIMEOUT_MINUTES = int(os.environ.get('JOB_TIMEOUT_MINUTES', '60'))
    
    # Hata Yönetimi
    MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))
    RETRY_DELAY = float(os.environ.get('RETRY_DELAY', '5.0'))
    
    # Chrome/Selenium User Agent
    USER_AGENT = os.environ.get('USER_AGENT', 
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # LinkedIn Specific
    LINKEDIN_BASE_URL = "https://www.linkedin.com"
    LINKEDIN_JOBS_SEARCH_URL = "https://www.linkedin.com/jobs/search/"
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'linkedin_scraper.log')
    
    @classmethod
    def init_app(cls, app):
        """Flask uygulamasını yapılandır"""
        # Gerekli klasörleri oluştur
        os.makedirs(cls.RESULTS_FOLDER, exist_ok=True)
        
        # Log klasörünü oluştur
        os.makedirs('logs', exist_ok=True)


class DevelopmentConfig(Config):
    """Geliştirme ortamı yapılandırması"""
    DEBUG = True
    SELENIUM_HEADLESS = False
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Üretim ortamı yapılandırması"""
    DEBUG = False
    SELENIUM_HEADLESS = True
    LOG_LEVEL = 'WARNING'


class TestConfig(Config):
    """Test ortamı yapılandırması"""
    TESTING = True
    SELENIUM_HEADLESS = True
    MAX_PAGES_LIMIT = 2
    DEFAULT_MAX_PAGES = 1


# Ortam yapılandırması mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestConfig,
    'default': DevelopmentConfig
}