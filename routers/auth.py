# routers/auth.py

## Импортирование модулей FastAPI ##
from fastapi import APIRouter, Body, Form
from fastapi import Depends, HTTPException, Header, Request

## Импортирование остальных модулей ##
import secrets

## Импортирование самописных модулей ##
from config import db, logger
from modules.auth import verify_access, hash_token, verify_hash_token

router = APIRouter(
    prefix='/api/auth',
    tags=['Auth']
)

@router.get("/register")
async def register(request: Request):
    new_token = secrets.token_hex(8)
    logger.printinf(f"""
            ===== Attention! =====
          
    [I] Find signals from Sky Client Agents.
    [+] New Token: {new_token}
    [D] IP-address agent: {request.client.host}
    
    [I] You need to copy the token into a special field within the client application Sky Client Agents.
    [I] But, if you application not Sky Client Agent, use SkyManager.
    [I] If this action was sent to you, ignore and check the safety of the server.
            ===== Attention! =====
    """)
    db.add_new_temp_reg(token=new_token, ip=request.client.host)
    
    # Шифровка токена.
    hashed_token = hash_token(new_token)
    return {"status": "OK", "hashed_token": hashed_token}

@router.post("/register")
async def register(request: Request, token: str = Form(...), client_hash: str = Form(...)):
    if not verify_hash_token(token, client_hash):
        raise HTTPException(status_code=403, detail="Forbidden")
    result = db.register_user(token, request.client.host)
    return {"status": "OK", "answer": result}

@router.delete("/unregister")
async def unregister(token: str = Depends(verify_access)):
    db.remove_user(token)
    return {"status": "OK", "message": "User has been removed."}

@router.get("/is_register")
async def is_register(token: str = Depends(verify_access)):
    return {"status": "OK", "is_register": db.check_user(token)}