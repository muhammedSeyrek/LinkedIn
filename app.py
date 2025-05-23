import time
import os
import threading
import json
import atexit
from datetime import datetime, timedelta
import uuid

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Local imports
from config import Config
from utils import (
    PerformanceMonitor, retry_on_failure, clean_old_files, validate_search_params,
    save_jobs_to_csv, create_job_summary, RateLimiter, generate_user_agent,
    detect_captcha_or_blocking, calculate_success_metrics, create_detailed_report,
    log_scraping_session, setup_application, cleanup_on_exit, handle_exceptions
)

# Flask uygulaması
app = Flask(__name__)
app.config.from_object(Config)

# Uygulama kurulumu
setup_application()

# Veri depolama için global değişkenler
active_jobs = {}  # Aktif arama işlerini saklar
completed_jobs = {}  # Tamamlanmış işleri saklar
job_lock = threading.Lock()  # Thread safety için

# Temizlik işlemlerini program kapanışında çalıştır
atexit.register(cleanup_on_exit)


class EnhancedLinkedInJobScraper:
    def __init__(self, headless=True, user_agent=None):
        """
        Gelişmiş LinkedIn iş ilanları tarayıcısı.
        """
        self.headless = headless
        self.user_agent = user_agent or generate_user_agent()
        self.driver = None
        self.wait = None
        self.performance_monitor = PerformanceMonitor()
        self.rate_limiter = RateLimiter()
        self.setup_driver()
    
    def setup_driver(self):
        """Selenium driver'ı kur"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Performans ve güvenlik ayarları
        chrome_options.add_argument(f"--user-agent={self.user_agent}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")  # Performans için
        chrome_options.add_argument("--disable-javascript")  # Opsiyonel
        
        # Memory optimizasyonu
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--max_old_space_size=4096")
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=chrome_options
            )
            self.wait = WebDriverWait(self.driver, Config.SELENIUM_TIMEOUT)
            
            # Selenium tespitini atlatmak için
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', 
                                      {"userAgent": self.user_agent})
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
        except Exception as e:
            raise Exception(f"Chrome driver kurulum hatası: {str(e)}")
    
    @retry_on_failure(max_retries=Config.MAX_RETRIES, delay=Config.RETRY_DELAY)
    def login(self, email, password):
        """LinkedIn hesabına giriş yap."""
        if not email or not password:
            return False
        
        try:
            self.driver.get("https://www.linkedin.com/login")
            self.rate_limiter.wait()
            
            # Login form elementlerini bekle
            email_field = self.wait.until(EC.element_to_be_clickable((By.ID, "username")))
            email_field.clear()
            email_field.send_keys(email)
            
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(password)
            
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Giriş sonucunu kontrol et
            try:
                self.wait.until(EC.any_of(
                    EC.url_contains("feed"),
                    EC.url_contains("check"),
                    EC.presence_of_element_located((By.CLASS_NAME, "global-nav"))
                ))
                
                # Captcha veya güvenlik kontrolü var mı?
                if detect_captcha_or_blocking(self.driver):
                    return False
                
                self.rate_limiter.record_success()
                return True
                
            except TimeoutException:
                self.rate_limiter.record_error()
                return False
                
        except Exception as e:
            self.rate_limiter.record_error()
            raise
    
    @handle_exceptions
    def search_jobs(self, keywords, location=None, job_types=None, experience_levels=None, 
                   remote_options=None, date_posted=None, max_pages=5, job_id=None, status_callback=None):
        """
        Gelişmiş iş ilanı arama.
        """
        self.performance_monitor.start()
        
        # URL oluştur
        search_url = self.build_search_url(
            keywords, location, job_types, experience_levels, 
            remote_options, date_posted
        )
        
        jobs_data = []
        current_page = 1
        
        try:
            # İlk sayfayı aç
            self.driver.get(search_url)
            self.rate_limiter.wait()
            
            # Popup'ları kapat
            self.handle_popups()
            
            while current_page <= max_pages:
                # Durum güncelle
                if status_callback:
                    progress = ((current_page - 1) / max_pages) * 100
                    status_callback(job_id, {
                        'status': 'running',
                        'progress': min(progress, 95),
                        'page': current_page,
                        'total_pages': max_pages,
                        'found_jobs': len(jobs_data),
                        'message': f'Sayfa {current_page} taranıyor...'
                    })
                
                # Captcha kontrolü
                if detect_captcha_or_blocking(self.driver):
                    raise Exception("LinkedIn tarafından engellendiniz. Lütfen daha sonra tekrar deneyin.")
                
                # Bu sayfadaki işleri al
                page_jobs = self.extract_jobs_from_page()
                jobs_data.extend(page_jobs)
                
                # Performans metrikleri güncelle
                self.performance_monitor.update(
                    pages_scraped=current_page,
                    jobs_found=len(jobs_data)
                )
                
                # Sonraki sayfaya geç
                if current_page < max_pages:
                    if not self.go_to_next_page():
                        break
                    self.rate_limiter.wait()
                
                current_page += 1
            
            # Final durum güncelle
            if status_callback:
                status_callback(job_id, {
                    'status': 'completed',
                    'progress': 100,
                    'page': current_page - 1,
                    'total_pages': max_pages,
                    'found_jobs': len(jobs_data),
                    'message': f'Arama tamamlandı! {len(jobs_data)} ilan bulundu.'
                })
            
            return jobs_data
            
        except Exception as e:
            self.performance_monitor.update(errors=1)
            if status_callback:
                status_callback(job_id, {
                    'status': 'failed',
                    'message': f'Hata: {str(e)}'
                })
            raise
    
    def build_search_url(self, keywords, location, job_types, experience_levels, remote_options, date_posted):
        """Arama URL'si oluştur"""
        base_url = "https://www.linkedin.com/jobs/search/?"
        params = [f"keywords={keywords.replace(' ', '%20')}"]
        
        if location:
            params.append(f"location={location.replace(' ', '%20')}")
        if job_types:
            params.append("f_JT=" + "%2C".join(job_types))
        if experience_levels:
            params.append("f_E=" + "%2C".join(map(str, experience_levels)))
        if remote_options:
            params.append("f_WT=" + "%2C".join(remote_options))
        if date_posted:
            params.append(f"f_TPR={date_posted}")
        
        return base_url + "&".join(params)
    
    def handle_popups(self):
        """Popup'ları ve modal pencereleri kapat"""
        popup_selectors = [
            "[data-test-modal] button[aria-label*='dismiss']",
            "[data-test-modal] button[aria-label*='close']",
            ".artdeco-modal__dismiss",
            ".msg-overlay-bubble-header__controls button",
            "button[aria-label*='Dismiss']",
            "[data-tracking-control-name*='dismiss']"
        ]
        
        for selector in popup_selectors:
            try:
                popup = self.driver.find_element(By.CSS_SELECTOR, selector)
                if popup.is_displayed():
                    popup.click()
                    time.sleep(1)
            except:
                continue
    
    def extract_jobs_from_page(self):
        """Sayfadaki tüm işleri çıkar"""
        self.scroll_page_gradually()
        
        job_cards = self.find_job_cards()
        jobs = []
        
        for card in job_cards:
            try:
                # Kartı görünür hale getir
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                time.sleep(0.5)
                
                job_data = self.extract_job_data_from_card(card)
                if job_data and job_data.get('title') != 'Başlık alınamadı':
                    jobs.append(job_data)
                
            except Exception as e:
                continue
        
        return jobs
    
    def find_job_cards(self):
        """İş kartlarını bul"""
        selectors = [
            ".job-search-card",
            ".jobs-search-results__list-item",
            ".scaffold-layout__list-item",
            "li[data-occludable-job-id]",
            ".jobs-search-results-list li"
        ]
        
        for selector in selectors:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                valid_cards = [card for card in cards if self.is_valid_job_card(card)]
                if valid_cards:
                    return valid_cards
            except:
                continue
        
        return []
    
    def is_valid_job_card(self, card):
        """Kartın geçerli olup olmadığını kontrol et"""
        try:
            if not card.is_displayed():
                return False
            
            title_selectors = [
                ".job-card-list__title",
                ".job-card-container__link",
                "h3 a"
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, selector)
                    if title_elem and title_elem.text.strip():
                        return True
                except:
                    continue
            
            return False
        except:
            return False
    
    def extract_job_data_from_card(self, card):
        """Karttan iş verilerini çıkar"""
        try:
            title = self.get_text_from_card(card, [
                ".job-card-list__title",
                ".job-card-container__link",
                "h3 a"
            ])
            
            company = self.get_text_from_card(card, [
                ".job-card-container__primary-description",
                ".job-card-list__subtitle",
                "h4 a"
            ])
            
            location = self.get_text_from_card(card, [
                ".job-card-container__metadata-item",
                ".job-card-list__metadata"
            ])
            
            link = self.get_link_from_card(card)
            
            date_posted = self.get_text_from_card(card, [
                ".job-card-list__posted-date",
                "time"
            ])
            
            return {
                "title": title or "Başlık alınamadı",
                "company": company or "Şirket adı alınamadı",
                "location": location or "Lokasyon alınamadı",
                "description": "Detay sayfasını ziyaret edin",
                "link": link or "Link alınamadı",
                "date_posted": date_posted or "Tarih alınamadı"
            }
            
        except Exception:
            return None
    
    def get_text_from_card(self, card, selectors):
        """Karttan metin al"""
        for selector in selectors:
            try:
                element = card.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except:
                continue
        return None
    
    def get_link_from_card(self, card):
        """Karttan link al"""
        selectors = [
            ".job-card-list__title a",
            ".job-card-container__link",
            "h3 a"
        ]
        
        for selector in selectors:
            try:
                link_elem = card.find_element(By.CSS_SELECTOR, selector)
                href = link_elem.get_attribute("href")
                if href:
                    return href
            except:
                continue
        return None
    
    def scroll_page_gradually(self):
        """Sayfayı kademeli olarak kaydır"""
        time.sleep(2)
        
        for i in range(3):
            self.driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)
        
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
    
    def go_to_next_page(self):
        """Sonraki sayfaya git"""
        selectors = [
            "button[aria-label='Next']:not([disabled])",
            ".artdeco-pagination__button--next:not([disabled])"
        ]
        
        for selector in selectors:
            try:
                next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                if next_button and next_button.is_enabled():
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(3)
                    return True
            except:
                continue
        
        return False
    
    def close(self):
        """Tarayıcıyı kapat"""
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass


def run_scraper_job(job_id, params):
    """Arkaplanda çalışacak gelişmiş tarayıcı işi"""
    with job_lock:
        if job_id not in active_jobs:
            return
        active_jobs[job_id]['status'] = 'running'
    
    scraper = None
    
    try:
        # Parametreleri doğrula
        validation_errors = validate_search_params(params)
        if validation_errors:
            raise Exception(f"Parametre hatası: {', '.join(validation_errors)}")
        
        # Parametreleri al
        keywords = params.get('keywords', '')
        location = params.get('location', '')
        job_types = params.get('job_types', [])
        experience_levels = params.get('experience_levels', [])
        remote_options = params.get('remote_options', [])
        date_posted = params.get('date_posted', '')
        max_pages = min(int(params.get('max_pages', 5)), Config.MAX_PAGES_LIMIT)
        email = params.get('email', '')
        password = params.get('password', '')
        
        # Durum güncellemesi için callback
        def update_status(job_id, status_data):
            with job_lock:
                if job_id in active_jobs:
                    active_jobs[job_id].update(status_data)
        
        # Scraper'ı başlat
        scraper = EnhancedLinkedInJobScraper(headless=Config.SELENIUM_HEADLESS)
        
        # LinkedIn'e giriş (opsiyonel)
        if email and password:
            login_success = scraper.login(email, password)
            if not login_success:
                update_status(job_id, {'message': 'LinkedIn girişi başarısız, misafir olarak devam ediliyor'})
        
        # İşleri ara
        jobs = scraper.search_jobs(
            keywords=keywords,
            location=location,
            job_types=job_types if job_types else None,
            experience_levels=experience_levels if experience_levels else None,
            remote_options=remote_options if remote_options else None,
            date_posted=date_posted if date_posted else None,
            max_pages=max_pages,
            job_id=job_id,
            status_callback=update_status
        )
        
        # Sonuçları kaydet
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"static/results/linkedin_jobs_{job_id}_{timestamp}.csv"
        saved_file = save_jobs_to_csv(jobs, filename)
        
        # Performans istatistikleri al
        performance_stats = scraper.performance_monitor.get_stats()
        scraper.performance_monitor.log_final_stats()
        
        # Detaylı rapor oluştur
        report = create_detailed_report(jobs, params, performance_stats)
        
        # Session'ı logla
        log_scraping_session(job_id, params, {'total_jobs_found': len(jobs)}, performance_stats)
        
        # İşi tamamlandı olarak işaretle
        with job_lock:
            if job_id in active_jobs:
                job_data = active_jobs[job_id]
                job_data.update({
                    'status': 'completed',
                    'progress': 100,
                    'found_jobs': len(jobs),
                    'result_file': saved_file,
                    'completed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'message': f'Arama tamamlandı! {len(jobs)} ilan bulundu.',
                    'performance_stats': performance_stats,
                    'report': report
                })
                
                # Tamamlanan işi completed_jobs'a taşı
                completed_jobs[job_id] = job_data
                active_jobs.pop(job_id, None)
        
    except Exception as e:
        error_message = str(e)
        
        # Hata durumunda işi başarısız olarak işaretle
        with job_lock:
            if job_id in active_jobs:
                active_jobs[job_id].update({
                    'status': 'failed',
                    'error': error_message,
                    'message': f'Hata oluştu: {error_message}',
                    'failed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Başarısız işi completed_jobs'a taşı
                completed_jobs[job_id] = active_jobs[job_id]
                active_jobs.pop(job_id, None)
    
    finally:
        # Kaynakları temizle
        if scraper:
            scraper.close()


# Flask Routes
@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')


@app.route('/start_search', methods=['POST'])
def start_search():
    """Yeni bir arama başlat"""
    try:
        # Eş zamanlı iş limitini kontrol et
        if len(active_jobs) >= Config.MAX_CONCURRENT_JOBS:
            flash(f'Maksimum {Config.MAX_CONCURRENT_JOBS} eş zamanlı arama yapabilirsiniz. Lütfen bekleyin.', 'warning')
            return redirect(url_for('jobs_list'))
        
        # Form verilerini al
        data = request.form
        
        # İş parametrelerini hazırla
        job_params = {
            'keywords': data.get('keywords', '').strip(),
            'location': data.get('location', '').strip(),
            'job_types': request.form.getlist('job_types'),
            'experience_levels': request.form.getlist('experience_levels'),
            'remote_options': request.form.getlist('remote_options'),
            'date_posted': data.get('date_posted', ''),
            'max_pages': min(int(data.get('max_pages', 5)), Config.MAX_PAGES_LIMIT),
            'email': data.get('email', '').strip(),
            'password': data.get('password', '').strip()
        }
        
        # Parametreleri doğrula
        validation_errors = validate_search_params(job_params)
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            return redirect(url_for('index'))
        
        # İş kimliği oluştur
        job_id = str(uuid.uuid4())
        
        # Yeni iş kaydı oluştur
        job_record = {
            'id': job_id,
            'status': 'queued',
            'progress': 0,
            'params': job_params,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'found_jobs': 0,
            'message': 'Arama sıraya alındı...'
        }
        
        # Aktif işlere ekle
        with job_lock:
            active_jobs[job_id] = job_record
        
        # Arka planda çalıştır
        thread = threading.Thread(target=run_scraper_job, args=(job_id, job_params))
        thread.daemon = True
        thread.start()
        
        flash('İş araması başlatıldı! İlerlemeyi kontrol sayfasından takip edebilirsiniz.', 'success')
        return redirect(url_for('job_status', job_id=job_id))
        
    except Exception as e:
        flash(f'Arama başlatılırken bir hata oluştu: {str(e)}', 'danger')
        return redirect(url_for('index'))


@app.route('/job_status/<job_id>')
def job_status(job_id):
    """İş durumu sayfası"""
    with job_lock:
        # Aktif işlerde ara
        job = active_jobs.get(job_id)
        
        # Tamamlanan işlerde ara
        if not job:
            job = completed_jobs.get(job_id)
    
    if not job:
        flash('Belirtilen iş bulunamadı.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('status.html', job=job, job_id=job_id)


@app.route('/api/job_status/<job_id>')
def api_job_status(job_id):
    """İş durumu API uç noktası"""
    with job_lock:
        # Aktif işlerde ara
        job = active_jobs.get(job_id)
        
        # Tamamlanan işlerde ara
        if not job:
            job = completed_jobs.get(job_id)
    
    if not job:
        return jsonify({'error': 'İş bulunamadı'}), 404
    
    # Hassas bilgileri kaldır
    safe_job = {k: v for k, v in job.items() if k not in ['params']}
    if 'params' in job:
        safe_params = {k: v for k, v in job['params'].items() if k not in ['email', 'password']}
        safe_job['params'] = safe_params
    
    return jsonify(safe_job)


@app.route('/jobs')
def jobs_list():
    """Tüm işlerin listesi"""
    with job_lock:
        # Aktif ve tamamlanan işleri birleştir
        all_jobs = []
        for job in active_jobs.values():
            all_jobs.append(job)
        for job in completed_jobs.values():
            all_jobs.append(job)
    
    # Tarihe göre sırala (en yeni önce)
    all_jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return render_template('jobs.html', jobs=all_jobs)


@app.route('/download/<job_id>')
def download_results(job_id):
    """İş sonuçlarını indir"""
    job = completed_jobs.get(job_id)
    
    if not job or 'result_file' not in job:
        flash('Belirtilen iş sonucu bulunamadı.', 'danger')
        return redirect(url_for('jobs_list'))
    
    try:
        return send_file(job['result_file'], as_attachment=True)
    except Exception as e:
        flash(f'Dosya indirme hatası: {str(e)}', 'danger')
        return redirect(url_for('jobs_list'))


@app.route('/delete_job/<job_id>', methods=['POST'])
def delete_job(job_id):
    """İşi sil"""
    with job_lock:
        # Aktif işse iptal et
        if job_id in active_jobs:
            active_jobs[job_id]['status'] = 'cancelled'
            completed_jobs[job_id] = active_jobs[job_id]
            active_jobs.pop(job_id, None)
        
        # Tamamlanan işi sil
        if job_id in completed_jobs:
            job = completed_jobs[job_id]
            
            # Dosyayı sil
            if 'result_file' in job and os.path.exists(job['result_file']):
                try:
                    os.remove(job['result_file'])
                except Exception as e:
                    flash(f'Dosya silme hatası: {str(e)}', 'warning')
            
            completed_jobs.pop(job_id, None)
            flash('İş başarıyla silindi.', 'success')
        else:
            flash('Silinecek iş bulunamadı.', 'danger')
    
    return redirect(url_for('jobs_list'))


@app.route('/api/stats')
def api_stats():
    """Sistem istatistikleri API"""
    with job_lock:
        stats = {
            'active_jobs': len(active_jobs),
            'completed_jobs': len(completed_jobs),
            'total_jobs': len(active_jobs) + len(completed_jobs),
            'success_rate': 0,
            'average_jobs_per_search': 0
        }
        
        if completed_jobs:
            successful_jobs = [job for job in completed_jobs.values() if job.get('status') == 'completed']
            stats['success_rate'] = (len(successful_jobs) / len(completed_jobs)) * 100
            
            total_found = sum(job.get('found_jobs', 0) for job in successful_jobs)
            if successful_jobs:
                stats['average_jobs_per_search'] = total_found / len(successful_jobs)
    
    return jsonify(stats)


@app.route('/cleanup', methods=['POST'])
def cleanup_old_jobs():
    """Eski işleri temizle"""
    try:
        cutoff_date = datetime.now() - timedelta(days=7)
        cleaned_count = 0
        
        with job_lock:
            jobs_to_remove = []
            for job_id, job in completed_jobs.items():
                try:
                    job_date = datetime.strptime(job.get('created_at', ''), '%Y-%m-%d %H:%M:%S')
                    if job_date < cutoff_date:
                        jobs_to_remove.append(job_id)
                except:
                    continue
            
            for job_id in jobs_to_remove:
                job = completed_jobs[job_id]
                
                # Dosyayı sil
                if 'result_file' in job and os.path.exists(job['result_file']):
                    try:
                        os.remove(job['result_file'])
                    except:
                        pass
                
                completed_jobs.pop(job_id, None)
                cleaned_count += 1
        
        # Dosya sistemi temizliği
        clean_old_files('static/results', max_age_days=7)
        clean_old_files('logs', max_age_days=7)
        
        flash(f'{cleaned_count} eski iş temizlendi.', 'success')
        
    except Exception as e:
        flash(f'Temizlik sırasında hata: {str(e)}', 'danger')
    
    return redirect(url_for('jobs_list'))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


# Uygulama başlangıç kontrolleri
with app.app_context():
    """İlk başlangıç işlemleri"""
    # Eski dosyaları temizle
    clean_old_files('static/results', max_age_days=30)
    clean_old_files('logs', max_age_days=7)


if __name__ == '__main__':
    # Geliştirme ortamında çalıştır
    app.run(
        debug=Config.DEBUG,
        host='0.0.0.0',
        port=5000,
        threaded=True
    )