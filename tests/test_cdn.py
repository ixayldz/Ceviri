import pytest
from unittest.mock import Mock, patch
from app.cdn import CDNManager
import boto3
from botocore.exceptions import ClientError

@pytest.fixture
def cdn_manager():
    return CDNManager()

@pytest.fixture
def mock_s3():
    with patch("boto3.client") as mock_client:
        yield mock_client

@pytest.fixture
def mock_cloudfront():
    with patch("boto3.client") as mock_client:
        yield mock_client

@pytest.mark.asyncio
async def test_upload_file(cdn_manager, mock_s3):
    """Dosya yükleme testi"""
    # Test verileri
    file_data = b"test audio data"
    file_key = "test.mp3"
    content_type = "audio/mpeg"
    
    # Mock S3 yanıtı
    mock_s3.return_value.put_object.return_value = {}
    
    # Dosya yükleme
    url = await cdn_manager.upload_file(
        file_data,
        file_key,
        content_type
    )
    
    # Assertions
    assert url is not None
    assert file_key in url
    mock_s3.return_value.put_object.assert_called_once()

@pytest.mark.asyncio
async def test_delete_file(cdn_manager, mock_s3, mock_cloudfront):
    """Dosya silme testi"""
    file_key = "test.mp3"
    
    # Mock yanıtlar
    mock_s3.return_value.delete_object.return_value = {}
    mock_cloudfront.return_value.create_invalidation.return_value = {}
    
    # Dosya silme
    result = await cdn_manager.delete_file(file_key)
    
    # Assertions
    assert result is True
    mock_s3.return_value.delete_object.assert_called_once()
    mock_cloudfront.return_value.create_invalidation.assert_called_once()

@pytest.mark.asyncio
async def test_get_signed_url(cdn_manager, mock_s3):
    """İmzalı URL oluşturma testi"""
    file_key = "test.mp3"
    test_url = "https://test-cdn.com/test.mp3"
    
    # Mock yanıt
    mock_s3.return_value.generate_presigned_url.return_value = test_url
    
    # URL oluşturma
    url = await cdn_manager.get_signed_url(file_key)
    
    # Assertions
    assert url == test_url
    mock_s3.return_value.generate_presigned_url.assert_called_once()

@pytest.mark.asyncio
async def test_upload_audio(cdn_manager):
    """Ses dosyası yükleme testi"""
    with patch.object(cdn_manager, "upload_file") as mock_upload:
        # Test verileri
        audio_data = b"test audio data"
        file_name = "test.mp3"
        user_id = 123
        test_url = "https://test-cdn.com/audio/123/test.mp3"
        
        # Mock yanıt
        mock_upload.return_value = test_url
        
        # Dosya yükleme
        url = await cdn_manager.upload_audio(
            audio_data,
            file_name,
            user_id
        )
        
        # Assertions
        assert url == test_url
        mock_upload.assert_called_once()

@pytest.mark.asyncio
async def test_cleanup_old_files(cdn_manager, mock_s3, mock_cloudfront):
    """Eski dosyaları temizleme testi"""
    # Mock yanıtlar
    mock_s3.return_value.get_paginator.return_value.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "old_file.mp3",
                    "LastModified": "2023-01-01"
                }
            ]
        }
    ]
    mock_s3.return_value.delete_objects.return_value = {}
    mock_cloudfront.return_value.create_invalidation.return_value = {}
    
    # Temizleme işlemi
    deleted_count = await cdn_manager.cleanup_old_files()
    
    # Assertions
    assert deleted_count == 1
    mock_s3.return_value.delete_objects.assert_called_once()
    mock_cloudfront.return_value.create_invalidation.assert_called_once()

@pytest.mark.asyncio
async def test_get_storage_stats(cdn_manager, mock_s3):
    """Depolama istatistikleri testi"""
    # Mock yanıt
    mock_s3.return_value.get_paginator.return_value.paginate.return_value = [
        {
            "Contents": [
                {
                    "Size": 1000,
                    "Key": "file1.mp3"
                },
                {
                    "Size": 2000,
                    "Key": "file2.mp3"
                }
            ]
        }
    ]
    
    # İstatistikleri al
    stats = await cdn_manager.get_storage_stats()
    
    # Assertions
    assert stats["total_size_bytes"] == 3000
    assert stats["total_files"] == 2
    assert "bucket_name" in stats

@pytest.mark.asyncio
async def test_error_handling(cdn_manager, mock_s3):
    """Hata yönetimi testi"""
    # S3 hatası simülasyonu
    mock_s3.return_value.put_object.side_effect = ClientError(
        {
            "Error": {
                "Code": "NoSuchBucket",
                "Message": "The specified bucket does not exist"
            }
        },
        "PutObject"
    )
    
    # Dosya yükleme denemesi
    url = await cdn_manager.upload_file(
        b"test data",
        "test.mp3",
        "audio/mpeg"
    )
    
    # Assertions
    assert url is None 