import time
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
import threading
import json
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Veri depolama için global değişkenler
active_jobs = {}  # Aktif arama işlerini saklar
completed_jobs = {}  # Tamamlanmış işleri saklar

# Uygulama klasörleri oluştur
os.makedirs('static/results', exist_ok=True)

class LinkedInJobScraper:
    def __init__(self, headless=True):
        """
        LinkedIn iş ilanları tarayıcısı.
        
        Args:
            headless (bool, optional): Tarayıcıyı görünmez modda çalıştırma
        """
        # Tarayıcı ayarları
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        
        # Kullanıcı ajanını değiştir (daha modern bir tarayıcı gibi görünmek için)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36")
        
        # Captcha önlemek için ek ayarlar
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        # Tarayıcıyı başlat
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        
        # Selenium tespitini atlatmak için
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'})
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def login(self, email, password):
        """LinkedIn hesabına giriş yap."""
        if not email or not password:
            print("Giriş yapılmadan devam ediliyor (bazı ilanlar görünmeyebilir)")
            return False
        
        try:
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(2)
            
            # Email ve şifre girişi
            self.driver.find_element(By.ID, "username").send_keys(email)
            self.driver.find_element(By.ID, "password").send_keys(password)
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
            
            # Giriş başarılı mı kontrol et
            try:
                self.wait.until(EC.url_contains("feed"))
                print("LinkedIn'e başarıyla giriş yapıldı")
                return True
            except TimeoutException:
                print("Giriş yapılamadı, doğrulama gerekebilir")
                return False
                
        except Exception as e:
            print(f"Giriş hatası: {e}")
            return False
    
    def search_jobs(self, keywords, location=None, job_types=None, experience_levels=None, 
                remote_options=None, date_posted=None, max_pages=5, job_id=None, status_callback=None):
        """
        Belirtilen kriterlere göre iş ilanlarını ara.
        
        Args:
            keywords (str): Aranacak anahtar kelimeler
            location (str, optional): İş lokasyonu
            job_types (list, optional): İş türleri ["F", "C", "P", "T", "I", "V"] 
            experience_levels (list, optional): Deneyim seviyeleri [1, 2, 3, 4, 5]
            remote_options (list, optional): Uzaktan çalışma seçenekleri ["1", "2", "3"]
            date_posted (str, optional): İlanın ne zaman yayınlandığı "r604800" (son 1 hafta), "r2592000" (son 30 gün)
            max_pages (int, optional): Taranacak maksimum sayfa sayısı
            job_id (str, optional): İşlem takibi için benzersiz iş kimliği
            status_callback (function, optional): Durum güncellemesi geri çağırma fonksiyonu
        
        Returns:
            list: İş ilanları listesi
        """
        # Arama URL'sini oluştur
        base_url = "https://www.linkedin.com/jobs/search/?"
        query_params = [f"keywords={keywords.replace(' ', '%20')}"]
        
        if location:
            query_params.append(f"location={location.replace(' ', '%20')}")
        
        if job_types:
            job_type_param = "f_JT=" + "%2C".join(job_types)
            query_params.append(job_type_param)
            
        if experience_levels:
            exp_param = "f_E=" + "%2C".join(map(str, experience_levels))
            query_params.append(exp_param)
            
        if remote_options:
            remote_param = "f_WT=" + "%2C".join(remote_options)
            query_params.append(remote_param)
            
        if date_posted:
            query_params.append(f"f_TPR={date_posted}")
        
        search_url = base_url + "&".join(query_params)
        
        # İş arama sayfasını aç
        self.driver.get(search_url)
        print(f"Arama URL'si: {search_url}")
        
        # Sayfanın tam olarak yüklenmesi için daha uzun bekleyin
        time.sleep(5)
        
        # Sayfaya insan gibi davranma ekleyin (scroll)
        self.driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(1)
        self.driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(1)
        self.driver.execute_script("window.scrollBy(0, -150);")
        time.sleep(2)
        
        # İlk olarak tüm iş ilanı linklerini toplayalım
        job_links = []
        page = 1
        
        while page <= max_pages:
            print(f"Sayfa {page} taranıyor - Linkler toplanıyor...")
            
            # Sayfayı yavaşça aşağı kaydır (daha fazla içerik yüklemek için)
            self.scroll_page_slowly()
            
            # LinkedIn'in farklı HTML yapılarına karşı birden fazla seçici dene
            job_listings_selectors = [
                "ul.jobs-search__results-list li",
                ".jobs-search-results__list-item",
                ".scaffold-layout__list-item",
                ".job-search-card"
            ]
            
            job_cards = []
            for selector in job_listings_selectors:
                try:
                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if job_cards:
                        print(f"İş kartları bulundu: {len(job_cards)} (seçici: {selector})")
                        break
                except:
                    continue
            
            if not job_cards:
                print("Bu sayfada iş kartları bulunamadı.")
                break
            
            # Tüm iş kartlarından linkleri çıkar
            for card in job_cards:
                try:
                    # Önce kartın görünür olmasını sağla
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    time.sleep(0.5)
                    
                    # Linki bul
                    link_selectors = ["a", "a.job-card-container__link", "a.job-card-list__title"]
                    link = None
                    
                    for link_selector in link_selectors:
                        try:
                            link_elem = card.find_element(By.CSS_SELECTOR, link_selector)
                            link = link_elem.get_attribute("href")
                            if link:
                                break
                        except:
                            continue
                            
                    if link and link not in job_links:
                        job_links.append(link)
                        print(f"Link bulundu: {link}")
                except Exception as e:
                    print(f"Link çıkarma hatası: {e}")
                    
            # Sonraki sayfa düğmesini bul ve tıkla
            try:
                next_button_selectors = [
                    "button.artdeco-pagination__button--next:not([disabled])",
                    ".artdeco-pagination__button--next:not(.artdeco-button--disabled)",
                    "li.artdeco-pagination__button--next button"
                ]
                
                next_button = None
                for selector in next_button_selectors:
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if next_button:
                            break
                    except:
                        continue
                
                if next_button and not next_button.get_attribute("disabled"):
                    # Düğmeyi görünür yap ve tıkla
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                    time.sleep(1)
                    next_button.click()
                    time.sleep(3)  # Sayfa yüklenene kadar bekle
                    page += 1
                else:
                    print("Sonraki sayfa bulunamadı veya son sayfadasınız.")
                    break
            except Exception as e:
                print(f"Sayfa çevirme hatası: {e}")
                break
        
        # Şimdi toplanan linklerdeki iş detaylarını al
        print(f"Toplam {len(job_links)} iş ilanı linki bulundu. Detaylar alınıyor...")
        jobs_data = []
        
        for index, job_link in enumerate(job_links):
            try:
                # İlerleme durumunu güncelle
                if status_callback:
                    progress = index / len(job_links) * 100
                    status_callback(job_id, {
                        'status': 'running', 
                        'progress': min(progress, 99),
                        'page': index + 1, 
                        'total_pages': len(job_links),
                        'found_jobs': len(jobs_data)
                    })
                
                # İş detay sayfasını aç
                self.driver.get(job_link)
                time.sleep(3)  # Sayfa yüklenene kadar bekle
                
                # Başlık
                title = self.get_text_with_multiple_selectors([
                    "h1.job-title", 
                    "h1.t-24", 
                    "h1.jobs-unified-top-card__job-title",
                    "h2.jobs-unified-top-card__job-title"
                ])
                
                # Şirket
                company = self.get_text_with_multiple_selectors([
                    "span.jobs-unified-top-card__company-name", 
                    "a.jobs-unified-top-card__company-name",
                    "div.jobs-unified-top-card__company-name"
                ])
                
                # Lokasyon
                location = self.get_text_with_multiple_selectors([
                    "span.jobs-unified-top-card__bullet", 
                    "span.jobs-unified-top-card__location",
                    "div.jobs-unified-top-card__metadata-container span.jobs-unified-top-card__location"
                ])
                
                # Açıklama
                description = self.get_text_with_multiple_selectors([
                    "div.jobs-description-content", 
                    "div.jobs-description__content",
                    "div.jobs-box__html-content"
                ])
                
                # Tarih
                date_posted = self.get_attribute_with_multiple_selectors([
                    "span.jobs-unified-top-card__posted-date", 
                    "span.jobs-details-job-summary__text--timestamp"
                ], "datetime")
                
                if not date_posted:
                    date_posted = self.get_text_with_multiple_selectors([
                        "span.jobs-unified-top-card__posted-date", 
                        "span.jobs-details-job-summary__text--timestamp"
                    ])
                
                job_data = {
                    "Başlık": title or "Başlık alınamadı",
                    "Şirket": company or "Şirket adı alınamadı",
                    "Lokasyon": location or "Lokasyon alınamadı",
                    "Açıklama": description or "Açıklama alınamadı",
                    "Link": job_link,
                    "Tarih": date_posted or "Tarih alınamadı"
                }
                
                jobs_data.append(job_data)
                print(f"İş ilanı detayları alındı: {job_data['Başlık']} - {job_data['Şirket']}")
                
            except Exception as e:
                print(f"İş detayları alınırken hata: {e}")
                continue
        
        # Son ilerleme güncellemesi
        if status_callback:
            status_callback(job_id, {
                'status': 'completed', 
                'progress': 100,
                'page': len(job_links), 
                'total_pages': len(job_links),
                'found_jobs': len(jobs_data)
            })
        
        return jobs_data

    def scroll_page_slowly(self):
        """Sayfayı kademeli olarak aşağı kaydır"""
        total_height = self.driver.execute_script("return document.body.scrollHeight")
        viewport_height = self.driver.execute_script("return window.innerHeight")
        scrolls = total_height // viewport_height
        
        for i in range(scrolls + 1):
            self.driver.execute_script(f"window.scrollTo(0, {i * viewport_height})")
            time.sleep(0.5)
        
        # Sayfanın en başına dön
        self.driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(1)

    def get_text_with_multiple_selectors(self, selectors):
        """Birden fazla seçici ile metin almayı dener"""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except:
                continue
        return None

    def get_attribute_with_multiple_selectors(self, selectors, attribute):
        """Birden fazla seçici ile özellik almayı dener"""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                value = element.get_attribute(attribute)
                if value:
                    return value
            except:
                continue
        return None
    
    def save_to_csv(self, jobs_data, filename="linkedin_jobs.csv"):
        """İş verilerini CSV dosyasına kaydet."""
        if not jobs_data:
            print("Kaydedilecek veri bulunamadı")
            return None
        
        df = pd.DataFrame(jobs_data)
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"{len(jobs_data)} iş ilanı {filename} dosyasına kaydedildi")
        return filename
    
    def close(self):
        """Tarayıcıyı kapat."""
        self.driver.quit()
        print("Tarayıcı kapatıldı")


def run_scraper_job(job_id, params):
    """Arkaplanda çalışacak tarayıcı işi"""
    active_jobs[job_id]['status'] = 'running'
    
    try:
        # Parametreleri al
        keywords = params.get('keywords', '')
        location = params.get('location', '')
        job_types = params.get('job_types', [])
        experience_levels = params.get('experience_levels', [])
        remote_options = params.get('remote_options', [])
        date_posted = params.get('date_posted', '')
        max_pages = int(params.get('max_pages', 3))
        
        # Durum güncellemesi için callback fonksiyonu
        def update_status(job_id, status_data):
            if job_id in active_jobs:
                active_jobs[job_id].update(status_data)
        
        # Tarayıcıyı başlat
        scraper = LinkedInJobScraper(headless=False)
        
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
        saved_file = scraper.save_to_csv(jobs, filename)
        
        # İşi tamamlandı olarak işaretle
        if job_id in active_jobs:
            job_data = active_jobs[job_id]
            job_data['status'] = 'completed'
            job_data['progress'] = 100
            job_data['found_jobs'] = len(jobs)
            job_data['result_file'] = saved_file
            job_data['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Tamamlanan işi completed_jobs'a taşı
            completed_jobs[job_id] = job_data
            active_jobs.pop(job_id, None)
        
    except Exception as e:
        # Hata durumunda işi başarısız olarak işaretle
        if job_id in active_jobs:
            active_jobs[job_id]['status'] = 'failed'
            active_jobs[job_id]['error'] = str(e)
            
            # Başarısız işi completed_jobs'a taşı
            completed_jobs[job_id] = active_jobs[job_id]
            active_jobs.pop(job_id, None)
    
    finally:
        # Tarayıcıyı kapat
        try:
            scraper.close()
        except:
            pass


@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')


@app.route('/start_search', methods=['POST'])
def start_search():
    """Yeni bir arama başlat"""
    try:
        # Form verilerini al
        data = request.form
        
        # İş parametrelerini hazırla
        job_params = {
            'keywords': data.get('keywords', ''),
            'location': data.get('location', ''),
            'job_types': request.form.getlist('job_types'),
            'experience_levels': request.form.getlist('experience_levels'),
            'remote_options': request.form.getlist('remote_options'),
            'date_posted': data.get('date_posted', ''),
            'max_pages': data.get('max_pages', 3)
        }
        
        # İş kimliği oluştur
        job_id = str(uuid.uuid4())
        
        # Yeni iş kaydı oluştur
        job_record = {
            'id': job_id,
            'status': 'queued',
            'progress': 0,
            'params': job_params,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'found_jobs': 0
        }
        
        # Aktif işlere ekle
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
    # Aktif işlerde ara
    job = active_jobs.get(job_id)
    
    # Tamamlanan işlerde ara
    if not job:
        job = completed_jobs.get(job_id)
    
    if not job:
        flash('Belirtilen iş bulunamadı.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('status.html', job=job)


@app.route('/api/job_status/<job_id>')
def api_job_status(job_id):
    """İş durumu API uç noktası"""
    # Aktif işlerde ara
    job = active_jobs.get(job_id)
    
    # Tamamlanan işlerde ara
    if not job:
        job = completed_jobs.get(job_id)
    
    if not job:
        return jsonify({'error': 'İş bulunamadı'}), 404
    
    return jsonify(job)


@app.route('/jobs')
def jobs_list():
    """Tüm işlerin listesi"""
    return render_template('jobs.html', 
                         active_jobs=active_jobs, 
                         completed_jobs=completed_jobs)


@app.route('/download/<job_id>')
def download_results(job_id):
    """İş sonuçlarını indir"""
    job = completed_jobs.get(job_id)
    
    if not job or 'result_file' not in job:
        flash('Belirtilen iş sonucu bulunamadı.', 'danger')
        return redirect(url_for('jobs_list'))
    
    return send_file(job['result_file'], as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)