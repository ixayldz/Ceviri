from google.cloud import speech_v1 as speech
from langdetect import detect
import logging

logger = logging.getLogger(__name__)

async def detect_language(audio_content: bytes) -> str:
    """
    Ses içeriğinden dili otomatik olarak algılar.
    Önce Google Speech-to-Text API'yi kullanır, başarısız olursa langdetect'i dener.
    """
    try:
        # Google Speech-to-Text ile dil algılama
        client = speech.SpeechClient()
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            enable_automatic_language_detection=True,
        )
        
        response = client.recognize(config=config, audio=audio)
        if response.results and response.results[0].language_code:
            detected_lang = response.results[0].language_code
            logger.info(f"Dil algılandı: {detected_lang}")
            return "tr-TR" if detected_lang.startswith("tr") else "en-US"
            
    except Exception as e:
        logger.error(f"Google Speech-to-Text dil algılama hatası: {e}")
        
    try:
        # Yedek olarak langdetect kullan
        # Önce metne çevir
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="tr-TR",  # Önce Türkçe dene
        )
        response = client.recognize(config=config, audio=audio)
        if response.results:
            text = response.results[0].alternatives[0].transcript
            detected_lang = detect(text)
            logger.info(f"Langdetect ile dil algılandı: {detected_lang}")
            return "tr-TR" if detected_lang == "tr" else "en-US"
            
    except Exception as e:
        logger.error(f"Langdetect dil algılama hatası: {e}")
    
    # Varsayılan olarak Türkçe döndür
    logger.warning("Dil algılanamadı, varsayılan olarak tr-TR kullanılıyor")
    return "tr-TR" 