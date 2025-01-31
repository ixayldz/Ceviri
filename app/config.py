import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
SECRET_KEY = os.getenv("SECRET_KEY")
REDIS_URL = os.getenv("REDIS_URL")

# CDN Yapılandırması
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
CDN_BUCKET_NAME = os.getenv("CDN_BUCKET_NAME")
CDN_DISTRIBUTION_ID = os.getenv("CDN_DISTRIBUTION_ID")
CDN_BASE_URL = os.getenv("CDN_BASE_URL")

# CDN önbellek ayarları
CDN_CACHE_DURATION = int(os.getenv("CDN_CACHE_DURATION", "31536000"))  # 1 yıl (saniye)
CDN_CLEANUP_DAYS = int(os.getenv("CDN_CLEANUP_DAYS", "30"))  # 30 gün