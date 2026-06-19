# routers/websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from modules.lock_storage import load_lock_state
from config import wsmanager

router = APIRouter(
    prefix='/api/sockets',
    tags=['Sockets Manager. WS']
)

@router.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await wsmanager.connect(websocket)
    
    # ПРИ СТАРТЕ/ПЕРЕПОДКЛЮЧЕНИИ: проверяем, если узел залочен — сразу пушим команду логаута
    state = load_lock_state()
    if state.get("is_locked"):
        payload = {
            "event": "lock_screen",
            "message": state.get("message"),
            "has_password": state.get("password_hash") is not None
        }
        await websocket.send_json(payload)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        wsmanager.disconnect(websocket)