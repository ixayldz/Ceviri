from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from app.schemas import UserCreate, User as UserSchema
from app.auth import get_current_user
from app.services.speech_to_text import transcribe_audio
from app.services.translation import translate_text
from app.services.text_to_speech import synthesize_speech
from app.services.language_detection import detect_language
from app.monitoring import record_translation, record_cache_hit, record_cache_miss
from sqlalchemy.orm import Session
from app.database import get_db
import asyncio

router = APIRouter(prefix="/v1")

@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Yeni kullanıcı kaydı oluştur.
    """
    return await register_user_handler(user, db)

@router.post("/translate")
async def translate_audio(
    audio_file: UploadFile = File(...),
    current_user: UserSchema = Depends(get_current_user)
):
    """
    Ses dosyasını çevir.
    """
    return await translate_audio_handler(audio_file, current_user)

@router.post("/tts")
async def text_to_speech(
    text: str,
    current_user: UserSchema = Depends(get_current_user)
):
    """
    Metni sese dönüştür.
    """
    return await text_to_speech_handler(text, current_user)

@router.get("/users/me", response_model=UserSchema)
async def read_users_me(current_user: UserSchema = Depends(get_current_user)):
    """
    Mevcut kullanıcının bilgilerini getir.
    """
    return current_user

@router.put("/users/me", response_model=UserSchema)
async def update_user(
    target_language: str = None,
    voice_preference: str = None,
    current_user: UserSchema = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Kullanıcı tercihlerini güncelle.
    """
    return await update_user_handler(
        target_language,
        voice_preference,
        current_user,
        db
    ) 