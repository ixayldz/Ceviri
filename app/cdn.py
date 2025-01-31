from typing import Optional
import boto3
from botocore.exceptions import ClientError
import structlog
from app.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    CDN_BUCKET_NAME,
    CDN_DISTRIBUTION_ID,
    CDN_BASE_URL
)

logger = structlog.get_logger()

class CDNManager:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        self.cloudfront = boto3.client(
            'cloudfront',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        self.bucket_name = CDN_BUCKET_NAME
        self.distribution_id = CDN_DISTRIBUTION_ID
        self.base_url = CDN_BASE_URL
    
    async def upload_file(
        self,
        file_data: bytes,
        file_key: str,
        content_type: str,
        cache_control: str = "max-age=31536000"  # 1 yıl
    ) -> Optional[str]:
        """Dosyayı S3'e yükle ve CDN URL'ini döndür"""
        try:
            # S3'e yükle
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_data,
                ContentType=content_type,
                CacheControl=cache_control
            )
            
            # CDN URL'ini oluştur
            return f"{self.base_url}/{file_key}"
            
        except Exception as e:
            logger.error("cdn_upload_error", error=str(e), file_key=file_key)
            return None
    
    async def delete_file(self, file_key: str) -> bool:
        """Dosyayı S3'ten sil ve CDN önbelleğini temizle"""
        try:
            # S3'ten sil
            self.s3.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            # CloudFront önbelleğini temizle
            self.cloudfront.create_invalidation(
                DistributionId=self.distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': 1,
                        'Items': [f"/{file_key}"]
                    },
                    'CallerReference': str(time.time())
                }
            )
            
            return True
            
        except Exception as e:
            logger.error("cdn_delete_error", error=str(e), file_key=file_key)
            return False
    
    async def get_signed_url(
        self,
        file_key: str,
        expires_in: int = 3600  # 1 saat
    ) -> Optional[str]:
        """İmzalı URL oluştur"""
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_key
                },
                ExpiresIn=expires_in
            )
            return url
            
        except Exception as e:
            logger.error("cdn_signed_url_error", error=str(e), file_key=file_key)
            return None
    
    async def upload_audio(
        self,
        audio_data: bytes,
        file_name: str,
        user_id: int
    ) -> Optional[str]:
        """Ses dosyasını CDN'e yükle"""
        file_key = f"audio/{user_id}/{file_name}"
        return await self.upload_file(
            audio_data,
            file_key,
            "audio/mpeg",
            "public, max-age=31536000"
        )
    
    async def get_audio_url(
        self,
        file_name: str,
        user_id: int,
        expires_in: int = 3600
    ) -> Optional[str]:
        """Ses dosyası için imzalı URL al"""
        file_key = f"audio/{user_id}/{file_name}"
        return await self.get_signed_url(file_key, expires_in)
    
    async def cleanup_old_files(self, days: int = 30) -> int:
        """Eski dosyaları temizle"""
        try:
            # N günden eski dosyaları listele
            cutoff = datetime.now() - timedelta(days=days)
            
            objects_to_delete = []
            paginator = self.s3.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    if obj['LastModified'].replace(tzinfo=None) < cutoff:
                        objects_to_delete.append({'Key': obj['Key']})
            
            if not objects_to_delete:
                return 0
            
            # Toplu silme işlemi
            self.s3.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': objects_to_delete}
            )
            
            # CloudFront önbelleğini temizle
            self.cloudfront.create_invalidation(
                DistributionId=self.distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(objects_to_delete),
                        'Items': [f"/{obj['Key']}" for obj in objects_to_delete]
                    },
                    'CallerReference': str(time.time())
                }
            )
            
            return len(objects_to_delete)
            
        except Exception as e:
            logger.error("cdn_cleanup_error", error=str(e))
            return 0
    
    async def get_storage_stats(self) -> dict:
        """Depolama istatistiklerini al"""
        try:
            # Toplam boyut ve dosya sayısı
            total_size = 0
            total_files = 0
            
            paginator = self.s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name):
                if 'Contents' in page:
                    total_files += len(page['Contents'])
                    total_size += sum(obj['Size'] for obj in page['Contents'])
            
            return {
                "total_size_bytes": total_size,
                "total_files": total_files,
                "bucket_name": self.bucket_name
            }
            
        except Exception as e:
            logger.error("cdn_stats_error", error=str(e))
            return {} 