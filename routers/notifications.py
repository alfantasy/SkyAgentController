from fastapi import APIRouter, Body, Depends
from config import wsmanager
from modules.auth import verify_access

router = APIRouter(
    prefix='/api/notifications',
    tags=['Notifications']
)

@router.post("/send/base")
async def send_notification(payload: dict = Body(...), token: str = Depends(verify_access)):
    await wsmanager.broadcast({"event": "notification", "desc": payload.get("desc"), "title": payload.get("title")})
    return {"status": "OK", "message": "Команда отправлена"}