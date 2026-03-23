import secrets
import hashlib
import time
from fastapi import HTTPException, Header, Request
from cryptography.hazmat.primitives.asymmetric import ed25519
from config import db

# Вспомогательная функция для получения ключа из БД
def get_master_pub_key():
    # Предположим, мы сохранили его в таблицу users с особым префиксом
    # Или ты можешь добавить self.sq.execute("CREATE TABLE IF NOT EXISTS config...")
    res = db.fetchone("SELECT token FROM users WHERE ip = 'MASTER_HUB_CONFIG'", ())
    return res[0] if res else None

async def verify_hub_request(request: Request, x_hub_signature: str, x_hub_timestamp: str):
    master_pub_hex = get_master_pub_key()
    if not master_pub_hex:
        return False

    # Проверка окна времени (60 сек)
    if not x_hub_timestamp or abs(int(time.time()) - int(x_hub_timestamp)) > 60:
        return False

    # Строка: "METHOD|PATH|TIMESTAMP"
    msg = f"{request.method}|{request.url.path}|{x_hub_timestamp}"
    
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(master_pub_hex))
        public_key.verify(bytes.fromhex(x_hub_signature), msg.encode('utf-8'))
        return True
    except Exception:
        return False

async def verify_access(
    request: Request, 
    authorization: str = Header(None),
    x_master_signature: str = Header(None),
    x_master_timestamp: str = Header(None)
):
    # ПУТЬ 1: Проверка по локальному токен (Tauri -> Standalone)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        if db.check_user(token):
            return token

    # ПУТЬ 2: Проверка подписи (MasterHub -> Standalone)
    if x_master_signature and x_master_timestamp:
        if await verify_hub_request(request, x_master_signature, x_master_timestamp):
            return "master_hub_authorized"

    raise HTTPException(status_code=401, detail="Access Denied: Invalid Token or Signature")

def hash_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()

def verify_hash_token(plain_token: str, provided_hash: str):
    # Проверяем, что хэш от введенного пользователем токена 
    # совпадает с тем хэшем, который мы выдали фронтенду ранее
    return hash_token(plain_token) == provided_hash