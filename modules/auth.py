import secrets
import hashlib
from fastapi import HTTPException, Header

from config import db

async def verify_access(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    if not db.check_user(token):
        raise HTTPException(status_code=403, detail="Forbidden")
    return token

def hash_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()

def verify_hash_token(plain_token: str, provided_hash: str):
    # Проверяем, что хэш от введенного пользователем токена 
    # совпадает с тем хэшем, который мы выдали фронтенду ранее
    return hash_token(plain_token) == provided_hash