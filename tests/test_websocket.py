import pytest
from fastapi.testclient import TestClient
from app.main import app
import asyncio
import json
from unittest.mock import patch, MagicMock
import base64

@pytest.fixture
def test_audio_data():
    # Test için örnek ses verisi
    return base64.b64decode("AAAA")  # Minimal WAV dosyası

@pytest.fixture
def websocket_client():
    return TestClient(app)

@pytest.fixture
def auth_token(websocket_client):
    # Test kullanıcısı oluştur ve token al
    response = websocket_client.post(
        "/register",
        json={"email": "ws_test@example.com", "password": "testpass"}
    )
    assert response.status_code == 201
    
    response = websocket_client.post(
        "/token",
        data={"username": "ws_test@example.com", "password": "testpass"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.mark.asyncio
async def test_websocket_connection(websocket_client, auth_token):
    with websocket_client.websocket_connect(
        f"/ws/translate?token={auth_token}"
    ) as websocket:
        assert websocket.connected

@pytest.mark.asyncio
async def test_websocket_authentication_failure(websocket_client):
    with pytest.raises(Exception):
        with websocket_client.websocket_connect("/ws/translate") as websocket:
            pass

@pytest.mark.asyncio
async def test_websocket_translation(websocket_client, auth_token, test_audio_data):
    with patch("app.services.speech_to_text.transcribe_audio") as mock_transcribe, \
         patch("app.services.translation.translate_text") as mock_translate, \
         patch("app.services.text_to_speech.synthesize_speech") as mock_tts:
        
        # Mock yanıtları ayarla
        mock_transcribe.return_value = "Merhaba"
        mock_translate.return_value = "Hello"
        mock_tts.return_value = b"audio_data"
        
        with websocket_client.websocket_connect(
            f"/ws/translate?token={auth_token}"
        ) as websocket:
            # Ses verisini gönder
            websocket.send_bytes(test_audio_data)
            
            # Yanıtı al ve kontrol et
            response = websocket.receive_json()
            assert response["transcribed_text"] == "Merhaba"
            assert response["translated_text"] == "Hello"
            assert response["audio_content"] is not None

@pytest.mark.asyncio
async def test_websocket_error_handling(websocket_client, auth_token, test_audio_data):
    with patch("app.services.speech_to_text.transcribe_audio") as mock_transcribe:
        # Hata fırlat
        mock_transcribe.side_effect = Exception("Test error")
        
        with websocket_client.websocket_connect(
            f"/ws/translate?token={auth_token}"
        ) as websocket:
            websocket.send_bytes(test_audio_data)
            response = websocket.receive_json()
            assert "error" in response

@pytest.mark.asyncio
async def test_websocket_performance(websocket_client, auth_token, test_audio_data):
    with patch("app.services.speech_to_text.transcribe_audio") as mock_transcribe, \
         patch("app.services.translation.translate_text") as mock_translate, \
         patch("app.services.text_to_speech.synthesize_speech") as mock_tts:
        
        mock_transcribe.return_value = "Test"
        mock_translate.return_value = "Test"
        mock_tts.return_value = b"audio_data"
        
        with websocket_client.websocket_connect(
            f"/ws/translate?token={auth_token}"
        ) as websocket:
            # Performans testi: 10 ardışık istek
            start_time = asyncio.get_event_loop().time()
            
            for _ in range(10):
                websocket.send_bytes(test_audio_data)
                response = websocket.receive_json()
                assert response["translated_text"] == "Test"
            
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time
            
            # Her istek 1 saniyeden az sürmeli
            assert duration / 10 < 1.0

@pytest.mark.asyncio
async def test_websocket_concurrent_connections(websocket_client, auth_token):
    max_connections = 5
    connections = []
    
    try:
        # Birden fazla bağlantı aç
        for _ in range(max_connections):
            ws = websocket_client.websocket_connect(
                f"/ws/translate?token={auth_token}"
            )
            connections.append(ws.__enter__())
            
        # Tüm bağlantıların açık olduğunu kontrol et
        for ws in connections:
            assert ws.connected
            
    finally:
        # Bağlantıları kapat
        for ws in connections:
            ws.__exit__(None, None, None) 