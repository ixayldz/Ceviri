from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: int
    email: str
    target_language: str
    voice_preference: str

    class Config:
        orm_mode = True