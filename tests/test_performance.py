import pytest
import asyncio
import aiohttp
import time
import statistics
from locust import HttpUser, task, between
import base64
from concurrent.futures import ThreadPoolExecutor
import numpy as np

class TranslationUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Kullanıcı kaydı ve token alma
        self.client.post("/register", json={
            "email": f"perf_test_{self.user_id}@example.com",
            "password": "testpass"
        })
        response = self.client.post("/token", data={
            "username": f"perf_test_{self.user_id}@example.com",
            "password": "testpass"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task
    def translate_audio(self):
        # Test ses dosyası
        audio_content = base64.b64decode("AAAA")
        response = self.client.post(
            "/translate",
            files={"audio_file": ("test.wav", audio_content)},
            headers=self.headers
        )
        assert response.status_code == 200

@pytest.mark.performance
class TestPerformance:
    @pytest.fixture(scope="class")
    async def test_client(self):
        async with aiohttp.ClientSession() as session:
            yield session
    
    @pytest.fixture(scope="class")
    async def auth_token(self, test_client):
        # Test kullanıcısı oluştur
        async with test_client.post(
            "http://localhost:8080/register",
            json={
                "email": "perf_test@example.com",
                "password": "testpass"
            }
        ) as response:
            assert response.status == 201
        
        # Token al
        async with test_client.post(
            "http://localhost:8080/token",
            data={
                "username": "perf_test@example.com",
                "password": "testpass"
            }
        ) as response:
            assert response.status == 200
            data = await response.json()
            return data["access_token"]
    
    async def measure_response_time(self, client, url, method="GET", **kwargs):
        start_time = time.time()
        async with getattr(client, method.lower())(url, **kwargs) as response:
            end_time = time.time()
            return end_time - start_time, response
    
    @pytest.mark.asyncio
    async def test_api_latency(self, test_client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}
        response_times = []
        
        # 100 istek at ve yanıt sürelerini ölç
        for _ in range(100):
            duration, response = await self.measure_response_time(
                test_client,
                "http://localhost:8080/users/me",
                method="GET",
                headers=headers
            )
            assert response.status == 200
            response_times.append(duration)
        
        # İstatistikleri hesapla
        avg_time = statistics.mean(response_times)
        p95_time = np.percentile(response_times, 95)
        p99_time = np.percentile(response_times, 99)
        
        # Performans kriterlerini kontrol et
        assert avg_time < 0.1  # Ortalama yanıt süresi 100ms'den az olmalı
        assert p95_time < 0.2  # 95. yüzdelik dilim 200ms'den az olmalı
        assert p99_time < 0.5  # 99. yüzdelik dilim 500ms'den az olmalı
    
    @pytest.mark.asyncio
    async def test_websocket_performance(self, auth_token):
        async def websocket_client():
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    f"ws://localhost:8080/ws/translate?token={auth_token}"
                ) as ws:
                    start_time = time.time()
                    
                    # 10 mesaj gönder ve yanıt al
                    for _ in range(10):
                        await ws.send_bytes(base64.b64decode("AAAA"))
                        await ws.receive_json()
                    
                    end_time = time.time()
                    return (end_time - start_time) / 10
        
        # 10 eşzamanlı WebSocket bağlantısı
        tasks = [websocket_client() for _ in range(10)]
        avg_times = await asyncio.gather(*tasks)
        
        # Performans kriterlerini kontrol et
        assert statistics.mean(avg_times) < 0.5  # Ortalama işlem süresi 500ms'den az olmalı
    
    @pytest.mark.asyncio
    async def test_concurrent_load(self, test_client, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}
        audio_content = base64.b64decode("AAAA")
        
        async def make_request():
            files = aiohttp.FormData()
            files.add_field("audio_file", audio_content, filename="test.wav")
            start_time = time.time()
            async with test_client.post(
                "http://localhost:8080/translate",
                data=files,
                headers=headers
            ) as response:
                end_time = time.time()
                assert response.status == 200
                return end_time - start_time
        
        # 50 eşzamanlı istek
        tasks = [make_request() for _ in range(50)]
        response_times = await asyncio.gather(*tasks)
        
        # İstatistikleri hesapla ve kontrol et
        avg_time = statistics.mean(response_times)
        max_time = max(response_times)
        assert avg_time < 1.0  # Ortalama süre 1 saniyeden az olmalı
        assert max_time < 2.0  # Maksimum süre 2 saniyeden az olmalı
    
    def test_memory_usage(self):
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Memory kullanımı 500MB'dan az olmalı
        assert memory_info.rss < 500 * 1024 * 1024  # 500MB 