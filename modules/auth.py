from fastapi import HTTPException, Header

from config import db

async def verify_access(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    if not db.check_user(token):
        raise HTTPException(status_code=403, detail="Forbidden")
    return token
