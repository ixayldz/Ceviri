# Voice Translator Deployment Kılavuzu

## Gereksinimler

### Altyapı
- Kubernetes cluster (min. 3 node)
- PostgreSQL veritabanı
- Redis
- Google Cloud hesabı
- Docker Registry

### Sistem Gereksinimleri
- CPU: Her pod için min. 200m
- RAM: Her pod için min. 256Mi
- Disk: Her node için min. 20GB

## Ortam Hazırlığı

### 1. Google Cloud Ayarları

1. Google Cloud projesini oluşturun
2. Gerekli API'leri aktifleştirin:
   - Speech-to-Text API
   - Translate API
   - Text-to-Speech API
3. Service account oluşturun ve credentials.json dosyasını indirin

### 2. Kubernetes Cluster Kurulumu

```bash
# Cluster oluştur
kubectl create namespace voice-translator

# Secret'ları oluştur
kubectl create secret generic app-secrets \
  --from-literal=database-url="postgresql://user:pass@host:5432/db" \
  --from-literal=redis-url="redis://host:6379/0" \
  --from-literal=secret-key="your-secret-key" \
  --namespace voice-translator

# Google Cloud credentials
kubectl create secret generic google-cloud-key \
  --from-file=credentials.json \
  --namespace voice-translator

# TLS sertifikası
kubectl create secret tls voice-translator-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  --namespace voice-translator
```

### 3. Monitoring Kurulumu

```bash
# Prometheus Operator kur
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace

# Grafana dashboard'ları import et
kubectl apply -f k8s/grafana-dashboards.yaml
```

## Deployment

### 1. Docker Image Build ve Push

```bash
# Image build
docker build -t your-registry/voice-translator:latest .

# Image push
docker push your-registry/voice-translator:latest
```

### 2. Kubernetes Deployment

```bash
# ConfigMap ve Secret'ları uygula
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# Deployment, Service ve Ingress'i uygula
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Prometheus alert kurallarını uygula
kubectl apply -f k8s/prometheus-rules.yaml
```

### 3. Database Migration

```bash
# Migration pod'unu çalıştır
kubectl apply -f k8s/migration-job.yaml
```

## Skalama ve Yüksek Erişilebilirlik

### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: voice-translator
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: voice-translator
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Pod Disruption Budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: voice-translator-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: voice-translator
```

## Monitoring ve Logging

### Prometheus Metrics

- `/metrics` endpoint'i üzerinden erişilebilir
- Önemli metrikler:
  - api_requests_total
  - api_response_time_seconds
  - ws_connections_active
  - translation_requests_total

### Grafana Dashboards

1. API Performance Dashboard
2. WebSocket Metrics Dashboard
3. Resource Usage Dashboard
4. Error Tracking Dashboard

### Log Aggregation

- Structured JSON formatında loglar
- Loglama seviyeleri:
  - INFO: Normal operasyonlar
  - WARNING: Potansiyel sorunlar
  - ERROR: Hatalar
  - CRITICAL: Kritik hatalar

## Bakım ve Güncelleme

### Zero-Downtime Deployment

```bash
# Rolling update
kubectl set image deployment/voice-translator \
  voice-translator=your-registry/voice-translator:new-version

# Rollback (gerekirse)
kubectl rollout undo deployment/voice-translator
```

### Database Backup

```bash
# Günlük backup
kubectl apply -f k8s/backup-cronjob.yaml
```

## Güvenlik

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: voice-translator-network-policy
spec:
  podSelector:
    matchLabels:
      app: voice-translator
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: database
    - namespaceSelector:
        matchLabels:
          name: redis
```

## Troubleshooting

### Pod Durumunu Kontrol Etme

```bash
kubectl get pods -n voice-translator
kubectl describe pod <pod-name> -n voice-translator
kubectl logs <pod-name> -n voice-translator
```

### Yaygın Sorunlar ve Çözümleri

1. Pod CrashLoopBackOff
   - Log'ları kontrol et
   - Environment variable'ları kontrol et
   - Resource limitlerini kontrol et

2. Database Bağlantı Hatası
   - Secret'ları kontrol et
   - Network policy'leri kontrol et
   - PostgreSQL durumunu kontrol et

3. Yüksek Latency
   - HPA ayarlarını kontrol et
   - Resource kullanımını kontrol et
   - Network sorunlarını kontrol et 