import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture
def test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(test_db):
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

def test_register_user(client):
    response = client.post(
        "/register",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"

def test_login_user(client):
    # Önce kullanıcı oluştur
    client.post(
        "/register",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    
    # Giriş yap
    response = client.post(
        "/token",
        data={"username": "test@example.com", "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_get_user_me(client):
    # Kullanıcı oluştur ve giriş yap
    client.post(
        "/register",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    login_response = client.post(
        "/token",
        data={"username": "test@example.com", "password": "testpassword"}
    )
    token = login_response.json()["access_token"]
    
    # Kullanıcı bilgilerini al
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"

def test_update_user_preferences(client):
    # Kullanıcı oluştur ve giriş yap
    client.post(
        "/register",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    login_response = client.post(
        "/token",
        data={"username": "test@example.com", "password": "testpassword"}
    )
    token = login_response.json()["access_token"]
    
    # Kullanıcı tercihlerini güncelle
    response = client.put(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_language": "en", "voice_preference": "female"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_language"] == "en"
    assert data["voice_preference"] == "female"

def test_translate_audio(client):
    # Bu test için mock audio dosyası gerekli
    pass

def test_text_to_speech(client):
    # Bu test için mock text gerekli
    pass 