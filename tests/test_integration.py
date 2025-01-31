import pytest
from fastapi.testclient import TestClient
from app.main import app
import asyncio
import aiohttp
import json
from sqlalchemy.orm import Session
from app.database import get_db
import os
import redis
import base64

@pytest.fixture(scope="module")
def test_app():
    client = TestClient(app)
    return client

@pytest.fixture(scope="module")
def test_db():
    # Test veritabanı bağlantısı
    db = next(get_db())
    yield db
    db.close()

@pytest.fixture(scope="module")
def redis_client():
    return redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

@pytest.fixture(scope="module")
def auth_headers(test_app):
    # Test kullanıcısı oluştur
    response = test_app.post(
        "/register",
        json={
            "email": "integration_test@example.com",
            "password": "testpass"
        }
    )
    assert response.status_code == 201
    
    # Token al
    response = test_app.post(
        "/token",
        data={
            "username": "integration_test@example.com",
            "password": "testpass"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}

def test_full_translation_flow(test_app, auth_headers, redis_client):
    # Test ses dosyası
    audio_content = base64.b64decode("AAAA")  # Minimal WAV dosyası
    
    # Ses dosyasını çevir
    response = test_app.post(
        "/translate",
        files={"audio_file": ("test.wav", audio_content)},
        headers=auth_headers
    )
    assert response.status_code == 200
    result = response.json()
    
    # Cache kontrolü
    cache_key = f"translation:{audio_content.hex()}:tr-TR:en"
    assert redis_client.get(cache_key) is not None
    
    # Çeviriyi sese dönüştür
    response = test_app.post(
        "/tts",
        json={"text": result["translation"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    assert "audio_content" in response.json()

@pytest.mark.asyncio
async def test_concurrent_requests(test_app, auth_headers):
    async def make_request():
        async with aiohttp.ClientSession() as session:
            audio_content = base64.b64decode("AAAA")
            files = aiohttp.FormData()
            files.add_field(
                "audio_file",
                audio_content,
                filename="test.wav"
            )
            headers = auth_headers.copy()
            async with session.post(
                "http://testserver/translate",
                data=files,
                headers=headers
            ) as response:
                return await response.json()
    
    # 10 eşzamanlı istek
    tasks = [make_request() for _ in range(10)]
    results = await asyncio.gather(*tasks)
    
    # Tüm isteklerin başarılı olduğunu kontrol et
    for result in results:
        assert "translation" in result

def test_database_integration(test_app, test_db, auth_headers):
    # Kullanıcı tercihlerini güncelle
    response = test_app.put(
        "/users/me",
        json={
            "target_language": "en",
            "voice_preference": "female"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    
    # Veritabanında güncellendiğini kontrol et
    user = test_db.query(User).filter(
        User.email == "integration_test@example.com"
    ).first()
    assert user.target_language == "en"
    assert user.voice_preference == "female"

def test_error_handling(test_app, auth_headers):
    # Geçersiz ses dosyası
    response = test_app.post(
        "/translate",
        files={"audio_file": ("test.wav", b"invalid_audio")},
        headers=auth_headers
    )
    assert response.status_code == 400
    
    # Geçersiz token
    response = test_app.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_websocket_integration(test_app, auth_headers):
    token = auth_headers["Authorization"].split(" ")[1]
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
            f"ws://testserver/ws/translate?token={token}"
        ) as ws:
            # Ses verisi gönder
            await ws.send_bytes(base64.b64decode("AAAA"))
            
            # Yanıt al
            response = await ws.receive_json()
            assert "transcribed_text" in response
            assert "translated_text" in response
            assert "audio_content" in response 