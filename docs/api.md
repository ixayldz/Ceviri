# Voice Translator API Dokümantasyonu

## Genel Bilgiler

- Base URL: `https://api.voice-translator.com`
- API Versiyonu: v1
- Kimlik Doğrulama: JWT Bearer token

## Kimlik Doğrulama

### Kullanıcı Kaydı

```http
POST /v1/register
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "secure_password"
}
```

**Yanıt:**
```json
{
    "id": 1,
    "email": "user@example.com",
    "target_language": "en",
    "voice_preference": "female"
}
```

### Token Alma

```http
POST /v1/token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=secure_password
```

**Yanıt:**
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "token_type": "bearer"
}
```

## REST API Endpoints

### Kullanıcı Bilgilerini Görüntüleme

```http
GET /v1/users/me
Authorization: Bearer <token>
```

**Yanıt:**
```json
{
    "id": 1,
    "email": "user@example.com",
    "target_language": "en",
    "voice_preference": "female"
}
```

### Kullanıcı Tercihlerini Güncelleme

```http
PUT /v1/users/me
Authorization: Bearer <token>
Content-Type: application/json

{
    "target_language": "en",
    "voice_preference": "female"
}
```

**Yanıt:**
```json
{
    "id": 1,
    "email": "user@example.com",
    "target_language": "en",
    "voice_preference": "female"
}
```

### Ses Dosyasını Çevirme

```http
POST /v1/translate
Authorization: Bearer <token>
Content-Type: multipart/form-data

audio_file: <binary_data>
```

**Yanıt:**
```json
{
    "translation": "Hello, how are you?"
}
```

### Metni Seslendirme

```http
POST /v1/tts
Authorization: Bearer <token>
Content-Type: application/json

{
    "text": "Hello, how are you?"
}
```

**Yanıt:**
```json
{
    "audio_content": "<base64_encoded_audio>"
}
```

## WebSocket API

### Gerçek Zamanlı Çeviri

```
WebSocket URL: ws://api.voice-translator.com/v1/ws/translate?token=<jwt_token>
```

**İstek Formatı:**
- Binary ses verisi

**Yanıt Formatı:**
```json
{
    "transcribed_text": "Merhaba, nasılsın?",
    "translated_text": "Hello, how are you?",
    "audio_content": "<base64_encoded_audio>"
}
```

**Hata Yanıtı:**
```json
{
    "error": "Hata mesajı"
}
```

## Limitler ve Kısıtlamalar

### Rate Limiting
- REST API: 60 istek/dakika
- WebSocket: 30 mesaj/dakika

### Bağlantı Limitleri
- Maksimum WebSocket bağlantısı: 100
- Kullanıcı başına maksimum bağlantı: 3

### Mesaj Boyutları
- Maksimum ses dosyası boyutu: 1MB
- Maksimum metin uzunluğu: 1000 karakter

## Hata Kodları

- 400: Geçersiz istek
- 401: Kimlik doğrulama hatası
- 403: Yetkisiz erişim
- 404: Kaynak bulunamadı
- 429: Rate limit aşıldı
- 500: Sunucu hatası

## WebSocket Hata Kodları

- 1008: Politika ihlali (bağlantı limiti aşıldı)
- 1011: Sunucu hatası 