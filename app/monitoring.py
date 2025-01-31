from prometheus_client import Counter, Histogram, Gauge, start_http_server
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
import time
import os
import structlog

logger = structlog.get_logger()

# API Metrics
REQUESTS_TOTAL = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['endpoint', 'method', 'status']
)

RESPONSE_TIME = Histogram(
    'api_response_time_seconds',
    'Response time in seconds',
    ['endpoint']
)

# Translation Metrics
TRANSLATION_REQUESTS = Counter(
    'translation_requests_total',
    'Total number of translation requests',
    ['source_language', 'target_language']
)

# Cache Metrics
CACHE_HITS = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_type']
)

CACHE_MISSES = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['cache_type']
)

# WebSocket Metrics
WS_CONNECTIONS_ACTIVE = Gauge(
    'ws_connections_active',
    'Number of active WebSocket connections'
)

WS_MESSAGES_TOTAL = Counter(
    'ws_messages_total',
    'Total number of WebSocket messages',
    ['direction', 'message_type']
)

WS_MESSAGE_SIZE = Histogram(
    'ws_message_size_bytes',
    'Size of WebSocket messages in bytes',
    ['direction']
)

WS_PROCESSING_TIME = Histogram(
    'ws_processing_time_seconds',
    'Time taken to process WebSocket messages',
    ['operation']
)

# Error Metrics
ERROR_TOTAL = Counter(
    'error_total',
    'Total number of errors',
    ['type', 'endpoint']
)

# Resource Usage Metrics
MEMORY_USAGE = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes'
)

CPU_USAGE = Gauge(
    'cpu_usage_percent',
    'CPU usage percentage'
)

def init_monitoring(app):
    # Prometheus metrics server'ı başlat
    start_http_server(int(os.getenv("PROMETHEUS_PORT", 8000)))
    
    # Sentry'yi yapılandır
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
        environment=os.getenv("ENVIRONMENT", "development")
    )
    
    @app.middleware("http")
    async def monitor_requests(request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Request metrikleri
            REQUESTS_TOTAL.labels(
                endpoint=request.url.path,
                method=request.method,
                status=response.status_code
            ).inc()
            
            # Yanıt süresi
            RESPONSE_TIME.labels(
                endpoint=request.url.path
            ).observe(time.time() - start_time)
            
            return response
            
        except Exception as e:
            # Hata metriği
            ERROR_TOTAL.labels(
                type=type(e).__name__,
                endpoint=request.url.path
            ).inc()
            
            # Sentry'ye bildir
            sentry_sdk.capture_exception(e)
            raise

def record_translation(source_lang: str, target_lang: str):
    """Çeviri isteğini kaydet"""
    TRANSLATION_REQUESTS.labels(
        source_language=source_lang,
        target_language=target_lang
    ).inc()

def record_cache_hit(cache_type: str):
    """Cache hit'i kaydet"""
    CACHE_HITS.labels(cache_type=cache_type).inc()

def record_cache_miss(cache_type: str):
    """Cache miss'i kaydet"""
    CACHE_MISSES.labels(cache_type=cache_type).inc()

# WebSocket Monitoring Functions
def record_ws_connection():
    """WebSocket bağlantısını kaydet"""
    WS_CONNECTIONS_ACTIVE.inc()

def record_ws_disconnection():
    """WebSocket bağlantı kopuşunu kaydet"""
    WS_CONNECTIONS_ACTIVE.dec()

def record_ws_message(direction: str, message_type: str, size: int):
    """WebSocket mesajını kaydet"""
    WS_MESSAGES_TOTAL.labels(
        direction=direction,
        message_type=message_type
    ).inc()
    WS_MESSAGE_SIZE.labels(direction=direction).observe(size)

def record_ws_processing_time(operation: str, duration: float):
    """WebSocket işlem süresini kaydet"""
    WS_PROCESSING_TIME.labels(operation=operation).observe(duration)

# Resource Monitoring
def update_resource_metrics():
    """Sistem kaynak kullanımını güncelle"""
    import psutil
    
    process = psutil.Process()
    
    # Memory kullanımı
    memory_info = process.memory_info()
    MEMORY_USAGE.set(memory_info.rss)
    
    # CPU kullanımı
    CPU_USAGE.set(process.cpu_percent()) 