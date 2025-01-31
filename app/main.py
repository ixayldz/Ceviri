from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from app.database import get_db, engine
from app.models import Base, User
from app.schemas import UserCreate, User as UserSchema
from app.auth import create_access_token, get_current_user
from app.services.speech_to_text import transcribe_audio
from app.services.translation import translate_text
from app.services.text_to_speech import synthesize_speech
from app.config import SECRET_KEY, RATE_LIMIT_PER_MINUTE, RATE_LIMIT_PER_HOUR
from jose import jwt
from datetime import timedelta
from passlib.context import CryptContext
import redis
from app.config import REDIS_URL
import asyncio
import logging
import structlog
from app.cdn import CDNManager
from typing import Optional

# Structured logging ayarları
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sesli Çeviri API",
    description="Sesli çeviri ve seslendirme API servisi",
    version="1.0.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Prodüksiyonda spesifik domainler belirtilmeli
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Güvenlik middleware'leri
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])  # Prodüksiyonda spesifik hostlar belirtilmeli
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
redis_client = redis.Redis.from_url(REDIS_URL)

cdn = CDNManager()

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

@app.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return UserSchema.from_orm(db_user)

@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserSchema)
def read_users_me(current_user: UserSchema = Depends(get_current_user)):
    return current_user

@app.put("/users/me", response_model=UserSchema)
def update_user(target_language: str = None, voice_preference: str = None, current_user: UserSchema = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user.id).first()
    if target_language:
        user.target_language = target_language
    if voice_preference:
        user.voice_preference = voice_preference
    db.commit()
    db.refresh(user)
    return UserSchema.from_orm(user)

@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında çalışacak işlemler"""
    # Redis bağlantısını başlat
    await init_redis_pool()
    
    # CDN bağlantısını kontrol et
    try:
        stats = await cdn.get_storage_stats()
        logger.info("cdn_connection_success", stats=stats)
    except Exception as e:
        logger.error("cdn_connection_error", error=str(e))
        raise

@app.get("/api/v1/audio/{user_id}/{file_name}")
async def get_audio_file(
    user_id: int,
    file_name: str,
    current_user = Depends(get_current_user)
):
    """Ses dosyası için imzalı URL döndür"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim")
        
    url = await cdn.get_audio_url(file_name, user_id)
    if not url:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
        
    return {"url": url}

@app.post("/api/v1/translate")
async def translate_audio(
    audio_file: UploadFile,
    source_lang: Optional[str] = None,
    target_lang: str = "tr",
    current_user = Depends(get_current_user)
):
    """Ses dosyasını çevir"""
    try:
        # Ses dosyasını oku
        audio_data = await audio_file.read()
        
        # CDN'e yükle
        cdn_url = await cdn.upload_audio(
            audio_data,
            audio_file.filename,
            current_user.id
        )
        
        if not cdn_url:
            raise HTTPException(
                status_code=500,
                detail="Dosya yüklenemedi"
            )
        
        # Çeviri işlemini gerçekleştir
        result = await translation_service.translate_audio(
            audio_data,
            source_lang,
            target_lang
        )
        
        # Sonucu döndür
        return {
            "source_text": result.source_text,
            "translated_text": result.translated_text,
            "source_lang": result.detected_language,
            "target_lang": target_lang,
            "audio_url": cdn_url
        }
        
    except Exception as e:
        logger.error(
            "translation_error",
            error=str(e),
            user_id=current_user.id
        )
        raise HTTPException(
            status_code=500,
            detail="Çeviri işlemi başarısız"
        )

@app.post("/tts")
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
async def text_to_speech(text: str, current_user: UserSchema = Depends(get_current_user)):
    try:
        logger.info("text_to_speech.start", user_id=current_user.id)
        language_code = "tr-TR" if current_user.target_language == "en" else "en-US"
        voice_gender = current_user.voice_preference
        
        cache_key = f"tts:{text}:{language_code}:{voice_gender}"
        cached_audio = redis_client.get(cache_key)
        
        if cached_audio:
            logger.info("text_to_speech.cache_hit", user_id=current_user.id)
            return {"audio_content": cached_audio}
        
        audio_content = await asyncio.to_thread(synthesize_speech, text, language_code, voice_gender)
        if not audio_content:
            logger.error("text_to_speech.synthesis_failed", user_id=current_user.id)
            raise HTTPException(status_code=400, detail="Ses sentezlenemedi")
        
        redis_client.set(cache_key, audio_content, ex=3600)
        logger.info("text_to_speech.success", user_id=current_user.id)
        return {"audio_content": audio_content}
        
    except Exception as e:
        logger.error("text_to_speech.error", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Sunucu hatası")

# Cache temizleme endpoint'i
@app.post("/admin/clear-cache")
async def clear_cache(current_user: UserSchema = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    try:
        redis_client.flushall()
        logger.info("cache.cleared", user_id=current_user.id)
        return {"message": "Önbellek temizlendi"}
    except Exception as e:
        logger.error("cache.clear_failed", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Önbellek temizlenemedi")