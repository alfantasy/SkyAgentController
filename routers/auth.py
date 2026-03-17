# routers/auth.py

## Импортирование модулей FastAPI ##
from fastapi import APIRouter, Form
from fastapi import Depends, HTTPException, Header, Request

## Импортирование остальных модулей ##
import secrets

## Импортирование самописных модулей ##
from config import db
from modules.auth import verify_access, hash_token, verify_hash_token

router = APIRouter(
    prefix='/api/auth',
    tags=['Auth']
)

@router.get("/register")
async def register(request: Request):
    new_token = secrets.token_hex(8)
    print(f"""
            ===== Внимание! =====
          
    [I] Обнаружен сигнал, отправленный на данного агента посредством клиентского приложения.
    [+] Новый токен: {new_token}
    [D] IP-адрес агента: {request.client.host}
    
    [I] Токен нужно вставить в специальное поле внутри клиентского приложения Sky Client Agents.
    [I] Если данное действие было отправлено не Вами, проигнорируйте и проверьте безопасность сервера.
            ===== Внимание! =====
    """)
    db.add_new_temp_reg(token=new_token, ip=request.client.host)
    
    # Шифровка токена.
    hashed_token = hash_token(new_token)
    return {"status": "OK", "hashed_token": hashed_token}

@router.post("/register")
async def register(request: Request, token: str = Form(...)):
    token = hash_token(token)
    if not verify_hash_token(token, token):
        raise HTTPException(status_code=403, detail="Forbidden")
    result = db.register_user(token, request.client.host)
    return {"status": "OK", "answer": result}

@router.delete("/unregister")
async def unregister(token: str = Depends(verify_access)):
    db.remove_user(token)
    return {"status": "OK", "message": "User has been removed."}