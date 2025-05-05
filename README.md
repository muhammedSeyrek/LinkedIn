# LinkedIn İş Tarayıcısı

Modern ve kullanıcı dostu web arayüzüne sahip, LinkedIn'deki iş ilanlarını taramak için geliştirilmiş bir uygulama.

![LinkedIn İş Tarayıcısı Ekran Görüntüsü](https://placeholder.pics/svg/800x400/DEDEDE/555555/LinkedIn%20%C4%B0%C5%9F%20Taray%C4%B1c%C4%B1s%C4%B1)

## Özellikler

- **Gelişmiş Arama Filtreleri**: İş türü, deneyim seviyesi, lokasyon ve daha fazlasına göre filtreleyin
- **Gerçek Zamanlı İlerleme İzleme**: İş tarama işlemini adım adım izleyin
- **Arka Plan İşlemi**: Tarama işlemi arkaplanda çalışır, böylece diğer işlerinize devam edebilirsiniz
- **CSV Dışa Aktarım**: Bulunan iş ilanlarını CSV formatında indirebilirsiniz
- **Responsive Tasarım**: Mobil cihazlar dahil tüm ekran boyutlarına uyumlu arayüz

## Kurulum

### Gereksinimler

- Python 3.8 veya daha yüksek
- Chrome tarayıcısı (Selenium için gerekli)
- pip (Python paket yöneticisi)

### Adımlar

1. Projeyi klonlayın veya indirin:
```bash
git clone https://github.com/kullanici/linkedin-is-tarayicisi.git
cd linkedin-is-tarayicisi
```

2. Sanal ortam oluşturun (opsiyonel ama önerilir):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac için
venv\Scripts\activate     # Windows için
```

3. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

4. Uygulamayı başlatın:
```bash
python app.py
```

5. Tarayıcınızda şu adrese gidin:
```
http://127.0.0.1:5000
```

## Gerekli Paketler (requirements.txt)

```
flask==2.3.3
pandas==2.0.3
selenium==4.11.2
webdriver-manager==3.8.6
```

## Nasıl Kullanılır

1. Ana sayfadaki formu kullanarak arama kriterlerinizi belirleyin:
   - Anahtar kelimeler (ör: "Python Developer", "Data Scientist")
   - Lokasyon (ör: "İstanbul, Türkiye", "Remote")
   - İş türü (Tam zamanlı, Yarı zamanlı, vb.)
   - Deneyim seviyesi
   - Uzaktan çalışma seçenekleri
   - İlan tarihi

2. "Aramayı Başlat" düğmesine tıklayın

3. Durum sayfasında ilerlemeyi izleyin:
   - Taranan sayfa sayısı
   - Bulunan iş ilanı sayısı
   - İlerleme yüzdesi

4. İşlem tamamlandığında, sonuçları CSV olarak indirin

5. "İşlerim" sayfasından önceki aramalarınızı görüntüleyebilir ve sonuçlarına erişebilirsiniz

## Proje Yapısı

```
linkedin-is-tarayicisi/
├── app.py                 # Ana Flask uygulaması
├── templates/             # HTML şablonları
│   ├── base.html          # Ana şablon
│   ├── index.html         # Ana sayfa
│   ├── status.html        # İş durumu sayfası
│   └── jobs.html          # İş listesi sayfası
├── static/                # Statik dosyalar
│   └── results/           # Çıktı CSV dosyaları
├── requirements.txt       # Gerekli paketler
└── README.md              # Bu dosya
```

## Özelleştirme

### Tarayıcı Ayarları

`app.py` dosyasındaki `LinkedInJobScraper` sınıfı içinde Selenium tarayıcı ayarlarını özelleştirebilirsiniz:

```python
chrome_options = Options()
chrome_options.add_argument("--headless")  # Görünmez modu devre dışı bırakmak için yorum satırına alın
chrome_options.add_argument("--no-sandbox")
# Diğer tarayıcı ayarları...
```

### Arama Parametreleri

Daha fazla arama parametresi eklemek istiyorsanız, hem HTML formunu (`templates/index.html`) hem de `app.py` dosyasındaki `start_search` fonksiyonunu güncellemeniz gerekir.

## Notlar

- LinkedIn, otomatik tarama işlemlerine karşı koruma mekanizmalarına sahiptir. Kısa süre içinde çok fazla istek göndermeniz durumunda IP adresiniz geçici olarak engellenebilir.
- Bu uygulama eğitim amaçlıdır ve LinkedIn ile resmi bir bağlantısı yoktur.
- Uygulamayı kullanarak elde ettiğiniz verileri kullanırken, ilgili gizlilik yasalarına ve LinkedIn kullanım şartlarına uymanız önemlidir.

## Lisans

MIT

## İletişim

Sorularınız veya önerileriniz için: muhammedseyrek00@gmail.com