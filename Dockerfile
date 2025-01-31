# Build stage
FROM python:3.8-slim as builder

WORKDIR /app

# Gerekli paketleri kopyala ve kur
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Final stage
FROM python:3.8-slim

# Prometheus için port
EXPOSE 8000
# FastAPI için port
EXPOSE 8080

WORKDIR /app

# Güvenlik için non-root kullanıcı oluştur
RUN useradd -m appuser && \
    chown -R appuser:appuser /app

# Builder stage'den wheel'ları kopyala
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Bağımlılıkları kur
RUN pip install --no-cache /wheels/*

# Uygulama kodlarını kopyala
COPY . .

# Non-root kullanıcıya geç
USER appuser

# Sağlık kontrolü için healthcheck ekle
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Uygulamayı başlat
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"] 