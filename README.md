# Sesli Çeviri API

Bu proje, sesli çeviri ve seslendirme hizmetleri sunan bir FastAPI uygulamasıdır.

## Özellikler

- Ses dosyalarını metne çevirme
- Metin çevirisi
- Metinden ses sentezleme
- WebSocket desteği ile gerçek zamanlı çeviri
- AWS CDN entegrasyonu
- Redis önbellekleme
- JWT tabanlı kimlik doğrulama
- Rate limiting
- Yapılandırılabilir dil ve ses tercihleri

## Gereksinimler

- Python 3.8+
- PostgreSQL
- Redis
- AWS hesabı (CDN için)
- Google Cloud hesabı (Speech-to-Text ve Translation API'leri için)

## Kurulum

1. Depoyu klonlayın:
```bash
git clone https://github.com/ixayldz/Ceviri.git
cd voice-translator
```

2. Sanal ortam oluşturun ve etkinleştirin:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows
```

3. Bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

4. Ortam değişkenlerini ayarlayın:
```bash
cp .env.example .env
# .env dosyasını düzenleyin
```

5. Veritabanını oluşturun:
```bash
alembic upgrade head
```

## Çalıştırma

Geliştirme sunucusunu başlatın:
```bash
uvicorn app.main:app --reload
```

API dokümantasyonuna erişin:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpointleri

- `POST /register`: Yeni kullanıcı kaydı
- `POST /token`: JWT token alma
- `GET /users/me`: Kullanıcı bilgilerini görüntüleme
- `PUT /users/me`: Kullanıcı tercihlerini güncelleme
- `POST /api/v1/translate`: Ses dosyası çevirisi
- `GET /api/v1/audio/{user_id}/{file_name}`: CDN'den ses dosyası alma
- `POST /tts`: Metinden ses sentezleme
- `WS /ws/translate`: WebSocket üzerinden gerçek zamanlı çeviri

## Testler

Testleri çalıştırın:
```bash
pytest
```

## Lisans

Bu proje Apache License 2.0 lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.
