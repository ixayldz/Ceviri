from redis import Redis
from typing import Optional, Any, Union
import json
import hashlib
import pickle
from datetime import timedelta
import structlog
from app.config import CACHE_TTL, MAX_CACHE_SIZE
from app.monitoring import record_cache_hit, record_cache_miss

logger = structlog.get_logger()

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url)
        self.default_ttl = int(CACHE_TTL)
        self.max_size = int(MAX_CACHE_SIZE)
        
    def _generate_key(self, prefix: str, *args) -> str:
        """Önbellek anahtarı oluştur"""
        key_parts = [str(arg) for arg in args]
        key_string = ":".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    async def get(self, key: str, cache_type: str) -> Optional[Any]:
        """Önbellekten veri al"""
        try:
            value = self.redis.get(key)
            if value is not None:
                record_cache_hit(cache_type)
                return pickle.loads(value)
            record_cache_miss(cache_type)
            return None
        except Exception as e:
            logger.error("cache_get_error", error=str(e), key=key)
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False
    ) -> bool:
        """Önbelleğe veri kaydet"""
        try:
            # Boyut kontrolü
            if len(pickle.dumps(value)) > self.max_size:
                logger.warning("cache_value_too_large", key=key)
                return False
            
            # Veriyi serialize et
            serialized = pickle.dumps(value)
            
            # TTL ayarla
            ttl = ttl or self.default_ttl
            
            # Kaydet
            if nx:
                return bool(self.redis.set(
                    key,
                    serialized,
                    ex=ttl,
                    nx=True
                ))
            else:
                return bool(self.redis.set(
                    key,
                    serialized,
                    ex=ttl
                ))
                
        except Exception as e:
            logger.error("cache_set_error", error=str(e), key=key)
            return False
    
    async def delete(self, key: str) -> bool:
        """Önbellekten veri sil"""
        try:
            return bool(self.redis.delete(key))
        except Exception as e:
            logger.error("cache_delete_error", error=str(e), key=key)
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Pattern'e uyan tüm verileri sil"""
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error("cache_clear_pattern_error", error=str(e), pattern=pattern)
            return 0
    
    async def get_or_set(
        self,
        key: str,
        func,
        ttl: Optional[int] = None,
        cache_type: str = "default"
    ) -> Any:
        """Önbellekten veri al, yoksa fonksiyonu çalıştır ve kaydet"""
        value = await self.get(key, cache_type)
        if value is not None:
            return value
            
        value = await func()
        if value is not None:
            await self.set(key, value, ttl)
        return value
    
    # Çeviri önbelleği için özel metodlar
    async def get_translation(
        self,
        audio_hash: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[str]:
        """Çeviri önbelleğinden veri al"""
        key = self._generate_key("translation", audio_hash, source_lang, target_lang)
        return await self.get(key, "translation")
    
    async def set_translation(
        self,
        audio_hash: str,
        source_lang: str,
        target_lang: str,
        translation: str,
        ttl: Optional[int] = None
    ) -> bool:
        """Çeviri önbelleğine veri kaydet"""
        key = self._generate_key("translation", audio_hash, source_lang, target_lang)
        return await self.set(key, translation, ttl)
    
    # TTS önbelleği için özel metodlar
    async def get_tts(
        self,
        text: str,
        lang: str,
        voice: str
    ) -> Optional[bytes]:
        """TTS önbelleğinden veri al"""
        key = self._generate_key("tts", text, lang, voice)
        return await self.get(key, "tts")
    
    async def set_tts(
        self,
        text: str,
        lang: str,
        voice: str,
        audio: bytes,
        ttl: Optional[int] = None
    ) -> bool:
        """TTS önbelleğine veri kaydet"""
        key = self._generate_key("tts", text, lang, voice)
        return await self.set(key, audio, ttl)
    
    # Kullanıcı önbelleği için özel metodlar
    async def get_user(self, user_id: int) -> Optional[dict]:
        """Kullanıcı önbelleğinden veri al"""
        key = self._generate_key("user", user_id)
        return await self.get(key, "user")
    
    async def set_user(
        self,
        user_id: int,
        user_data: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """Kullanıcı önbelleğine veri kaydet"""
        key = self._generate_key("user", user_id)
        return await self.set(key, user_data, ttl or 300)  # 5 dakika
    
    async def invalidate_user(self, user_id: int) -> bool:
        """Kullanıcı önbelleğini temizle"""
        key = self._generate_key("user", user_id)
        return await self.delete(key)
    
    # Rate limiting için özel metodlar
    async def increment_rate_limit(
        self,
        key: str,
        ttl: int
    ) -> int:
        """Rate limit sayacını artır"""
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            result = pipe.execute()
            return result[0]
        except Exception as e:
            logger.error("rate_limit_error", error=str(e), key=key)
            return 0
    
    # Önbellek temizleme ve bakım
    async def cleanup_expired(self) -> int:
        """Süresi dolmuş verileri temizle"""
        try:
            script = """
            local keys = redis.call('keys', ARGV[1])
            local count = 0
            for i, key in ipairs(keys) do
                if redis.call('ttl', key) <= 0 then
                    redis.call('del', key)
                    count = count + 1
                end
            end
            return count
            """
            return self.redis.eval(script, 0, "*")
        except Exception as e:
            logger.error("cache_cleanup_error", error=str(e))
            return 0
    
    async def get_stats(self) -> dict:
        """Önbellek istatistiklerini al"""
        try:
            info = self.redis.info()
            return {
                "used_memory": info["used_memory"],
                "hits": info["keyspace_hits"],
                "misses": info["keyspace_misses"],
                "keys": info["db0"]["keys"]
            }
        except Exception as e:
            logger.error("cache_stats_error", error=str(e))
            return {} 