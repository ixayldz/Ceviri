from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from app.auth import get_current_user_ws
from app.services.speech_to_text import transcribe_audio
from app.services.translation import translate_text
from app.services.text_to_speech import synthesize_speech
from app.services.language_detection import detect_language
from app.monitoring import (
    record_translation,
    record_ws_connection,
    record_ws_disconnection,
    record_ws_message,
    record_ws_processing_time
)
import json
import asyncio
from typing import Dict, Set
import time
from datetime import datetime, timedelta
import structlog
from fastapi.websockets import WebSocketState
from prometheus_client import Counter

logger = structlog.get_logger()

# WebSocket limitleri
MAX_CONNECTIONS_PER_USER = 3
MAX_TOTAL_CONNECTIONS = 100
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
MAX_MESSAGES_PER_MINUTE = 30
MESSAGE_TIMEOUT = 60  # saniye

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}
        
    async def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        user_requests = self.requests.get(user_id, [])
        
        # Eski istekleri temizle
        user_requests = [req for req in user_requests if now - req < self.time_window]
        
        if len(user_requests) >= self.max_requests:
            return False
            
        user_requests.append(now)
        self.requests[user_id] = user_requests
        return True

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.total_connections = 0
        self.rate_limiter = RateLimiter(
            max_requests=MAX_MESSAGES_PER_MINUTE,
            time_window=60
        )
        
    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        # Toplam bağlantı limitini kontrol et
        if self.total_connections >= MAX_TOTAL_CONNECTIONS:
            await websocket.close(code=1008, reason="Maksimum bağlantı sayısına ulaşıldı")
            return False
            
        # Kullanıcı başına bağlantı limitini kontrol et
        user_connections = self.active_connections.get(user_id, set())
        if len(user_connections) >= MAX_CONNECTIONS_PER_USER:
            await websocket.close(code=1008, reason="Maksimum kullanıcı bağlantı sayısına ulaşıldı")
            return False
            
        # Bağlantıyı kabul et
        await websocket.accept()
        
        # Bağlantıyı kaydet
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        self.total_connections += 1
        
        # Metriği güncelle
        record_ws_connection()
        return True

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            self.total_connections -= 1
            record_ws_disconnection()

    async def validate_message(self, message: bytes) -> bool:
        # Mesaj boyutunu kontrol et
        if len(message) > MAX_MESSAGE_SIZE:
            return False
        return True

manager = ConnectionManager()

@router.websocket("/ws/translate")
async def websocket_endpoint(websocket: WebSocket, user = Depends(get_current_user_ws)):
    if not await manager.connect(websocket, user.id):
        return
        
    try:
        while True:
            try:
                # Rate limiting kontrolü
                if not await manager.rate_limiter.is_allowed(user.id):
                    await websocket.send_json({
                        "error": "Rate limit aşıldı. Lütfen biraz bekleyin."
                    })
                    continue
                
                # Timeout ile ses verisi al
                try:
                    audio_data = await asyncio.wait_for(
                        websocket.receive_bytes(),
                        timeout=MESSAGE_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    await websocket.send_json({
                        "error": "Bağlantı zaman aşımına uğradı"
                    })
                    continue
                
                # Mesaj boyutunu kontrol et
                if not await manager.validate_message(audio_data):
                    await websocket.send_json({
                        "error": "Mesaj boyutu çok büyük"
                    })
                    continue
                
                # Mesaj metriğini kaydet
                record_ws_message("receive", "audio", len(audio_data))
                
                start_time = time.time()
                try:
                    # Dil algılama
                    source_language = await detect_language(audio_data)
                    
                    # Metne dönüştür
                    transcribed_text = await asyncio.to_thread(
                        transcribe_audio,
                        audio_data,
                        source_language
                    )
                    
                    if not transcribed_text:
                        await websocket.send_json({
                            "error": "Ses metne dönüştürülemedi"
                        })
                        continue
                    
                    # Hedef dile çevir
                    target_language = user.target_language
                    translated_text = await asyncio.to_thread(
                        translate_text,
                        transcribed_text,
                        target_language
                    )
                    
                    if not translated_text:
                        await websocket.send_json({
                            "error": "Metin çevirilemedi"
                        })
                        continue
                    
                    # Sese dönüştür
                    audio_content = await asyncio.to_thread(
                        synthesize_speech,
                        translated_text,
                        target_language,
                        user.voice_preference
                    )
                    
                    # İşlem süresini kaydet
                    processing_time = time.time() - start_time
                    record_ws_processing_time("full_translation", processing_time)
                    
                    # Sonuçları gönder
                    response = {
                        "transcribed_text": transcribed_text,
                        "translated_text": translated_text,
                        "audio_content": audio_content.hex() if audio_content else None
                    }
                    await websocket.send_json(response)
                    
                    # Yanıt metriğini kaydet
                    record_ws_message("send", "translation", len(str(response)))
                    
                    # Çeviri metriğini kaydet
                    record_translation(source_language, target_language)
                    
                except Exception as e:
                    logger.error(
                        "websocket_processing_error",
                        error=str(e),
                        user_id=user.id
                    )
                    await websocket.send_json({
                        "error": str(e)
                    })
                    
            except WebSocketDisconnect:
                break
                
    finally:
        manager.disconnect(websocket, user.id) 