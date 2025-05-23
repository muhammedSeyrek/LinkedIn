import os
import time
import csv
import logging
from datetime import datetime, timedelta

# Basit logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_application():
    """Uygulama kurulum işlemleri"""
    os.makedirs('logs', exist_ok=True)
    os.makedirs('static/results', exist_ok=True)
    os.makedirs('temp', exist_ok=True)
    logger.info("Uygulama kurulumu tamamlandı")

def validate_search_params(params):
    """Arama parametrelerini doğrula"""
    errors = []
    if not params.get('keywords', '').strip():
        errors.append("Anahtar kelimeler zorunludur")
    
    max_pages = params.get('max_pages', 5)
    try:
        max_pages = int(max_pages)
        if max_pages < 1 or max_pages > 20:
            errors.append("Sayfa sayısı 1-20 arasında olmalıdır")
    except (ValueError, TypeError):
        errors.append("Geçersiz sayfa sayısı")
    
    return errors

def save_jobs_to_csv(jobs_data, filename):
    """İş verilerini CSV'ye kaydet"""
    if not jobs_data:
        logger.warning("Kaydedilecek iş verisi bulunamadı")
        return None
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['title', 'company', 'location', 'description', 'link', 'date_posted']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(jobs_data)
        
        logger.info(f"{len(jobs_data)} iş ilanı {filename} dosyasına kaydedildi")
        return filename
        
    except Exception as e:
        logger.error(f"CSV kaydetme hatası: {str(e)}")
        raise

def clean_old_files(folder_path, max_age_days=30):
    """Eski dosyaları temizle"""
    if not os.path.exists(folder_path):
        return
    now = time.time()
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)
            if file_age > max_age_days * 86400:
                try:
                    os.remove(file_path)
                    logger.info(f"Silindi: {file_path}")
                except Exception as e:
                    logger.warning(f"Dosya silinemedi: {file_path} - {str(e)}")

def create_job_summary(jobs_data, search_params):
    """İş araması özeti oluştur"""
    return f"{len(jobs_data)} iş ilanı bulundu"

def cleanup_on_exit():
    """Çıkış sırasında temizlik işlemleri"""
    logger.info("Uygulama kapatılıyor...")

class PerformanceMonitor:
    """Basit performans izleme sınıfı"""
    
    def __init__(self):
        self.start_time = None
        self.metrics = {}
    
    def start(self):
        self.start_time = time.time()
        self.metrics = {'start_time': self.start_time}
        logger.info("Performans izleme başlatıldı")
    
    def update(self, pages_scraped=0, jobs_found=0, errors=0):
        if self.start_time is None:
            return
        self.metrics.update({
            'pages_scraped': pages_scraped,
            'jobs_found': jobs_found,
            'errors': errors,
            'elapsed_time': time.time() - self.start_time
        })
    
    def get_stats(self):
        if self.start_time is None:
            return {}
        
        elapsed = time.time() - self.start_time
        stats = {
            'elapsed_time': elapsed,
            'pages_per_minute': (self.metrics.get('pages_scraped', 0) / elapsed * 60) if elapsed > 0 else 0,
            'jobs_per_minute': (self.metrics.get('jobs_found', 0) / elapsed * 60) if elapsed > 0 else 0
        }
        return stats
    
    def log_final_stats(self):
        stats = self.get_stats()
        logger.info(f"Scraping tamamlandı - İstatistikler: {stats}")

class RateLimiter:
    """Basit hız sınırlayıcı sınıfı"""
    
    def __init__(self, min_delay=2.0, max_delay=5.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = 0
        self.consecutive_errors = 0
    
    def wait(self):
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        delay = self.min_delay + (self.consecutive_errors * 0.5)
        delay = min(delay, self.max_delay)
        
        if elapsed < delay:
            sleep_time = delay - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def record_error(self):
        self.consecutive_errors += 1
    
    def record_success(self):
        self.consecutive_errors = 0

def retry_on_failure(max_retries=3, delay=2):
    """Hata durumunda yeniden deneme decorator'ı"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Deneme {attempt + 1}/{max_retries + 1} başarısız: {str(e)}")
                        time.sleep(delay * (attempt + 1))
                    else:
                        logger.error(f"Tüm denemeler başarısız: {str(e)}")
            
            raise last_exception
        return wrapper
    return decorator

def handle_exceptions(func):
    """Genel exception handler decorator"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fonksiyon {func.__name__} içinde hata: {str(e)}")
            raise
    return wrapper

def generate_user_agent():
    """Rastgele user agent üret"""
    return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def detect_captcha_or_blocking(driver):
    """Captcha veya engellenme durumunu tespit et"""
    try:
        page_text = driver.page_source.lower()
        captcha_indicators = ['captcha', 'robot', 'unusual traffic', 'verify you are human']
        
        for indicator in captcha_indicators:
            if indicator in page_text:
                return True
    except:
        pass
    
    return False

def create_detailed_report(jobs_data, search_params, performance_stats):
    """Detaylı rapor oluştur"""
    return {
        'toplam_ilan': len(jobs_data),
        'arama_tarihi': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'performans': performance_stats
    }

def log_scraping_session(job_id, search_params, results_summary, performance_stats):
    """Scraping oturumunu logla"""
    logger.info(f"Session tamamlandı - Job ID: {job_id}, Sonuçlar: {results_summary}")

def calculate_success_metrics(*args, **kwargs):
    return {}

def log_scraping_session(job_id, params, meta, performance_stats):
    logger.info(f"Session log: {job_id}, params: {params}, meta: {meta}, perf: {performance_stats}")