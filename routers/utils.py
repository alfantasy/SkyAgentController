from fastapi import APIRouter, Body, Depends, HTTPException, Request
from typing import List, Optional
from pydantic import BaseModel, Field

from modules.auth import verify_access
from config import system, db, logger, wsmanager

import platform, subprocess

from modules.lock_storage import load_lock_state, save_lock_state, verify_password

router = APIRouter(
    prefix='/api/utils',
    tags=['Utils']
)

ALLOWED_COMMANDS = ["dir", "ls", "ping", "netstat", "ipconfig", "ifconfig", "systeminfo", "whoami", "ssh"]

class ScreenshotRequest(BaseModel):
    monitor_id: int = 1

class TerminalRequest(BaseModel):
    command: str

class TelemetryRequest(BaseModel):
    metrics: List[str] = Field(
        default=["cpu", "ram"], 
        description="Список системных метрик для сбора с узла"
    )

@router.get("/ping")
async def ping_to_device():
    return {"status": "OK"}

@router.get("/monitors")
async def get_monitors(token: str = Depends(verify_access)):
    try:
        return {"status": "OK", "monitors": system.get_monitors()}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@router.get("/screenshot") # Меняем на GET для простоты работы с тегом <img>
async def make_an_screenshot(
    monitor_id: int = 1, 
    quality: int = 80, 
    token: str = Depends(verify_access) # Токен будет проверяться из Query параметров
):
    try:
        return system.screenshot_reject(monitor_id, quality)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sysinfo")
async def get_sys_info(
    payload: TelemetryRequest = Body(...),
    token: str = Depends(verify_access)
):
    try:
        # payload.metrics — это как раз твой чистый Python-лист: ['cpu', 'ram', ...]
        info_system_reject = system.info_system(payload.metrics)
        
        return {
            "status": "OK", 
            "data": info_system_reject, 
            "who_ami": token
        }
    except Exception as e:
        return {
            "status": "ERROR", 
            "message": str(e)
        }
    
@router.get("/os_info")
async def get_os_info(token: str = Depends(verify_access)):
    """
    Возвращает тип операционной системы узла.
    Пример ответа: {"status": "OK", "os": "Windows"}
    """
    return {
        "status": "OK", 
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version()
    }

@router.post("/terminal")
async def execute_command(req: TerminalRequest, token: str = Depends(verify_access)):
    # 1. Простая фильтрация
    command = req.command
    base_cmd = command.split()[0].lower()
    if base_cmd not in ALLOWED_COMMANDS:
        return {"status": "ERROR", "message": f"Команда '{base_cmd}' из соображений безопасности выполнения терминальных операнд. Поддерживаемые команды: [{', '.join(ALLOWED_COMMANDS)}]"}

    try:
        # 2. Выполнение (ограничение 10 секунд)
        # shell=True нужен для встроенных команд Windows (типа dir), но будь осторожен
        process = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=10,
            encoding='cp866' # Для корректного отображения кириллицы в консоли Windows
        )
        
        return {
            "status": "OK", 
            "output": process.stdout if process.returncode == 0 else process.stderr
        }
    except subprocess.TimeoutExpired:
        return {"status": "ERROR", "message": "Превышено время ожидания (Timeout)"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}    

@router.get("/process/list")
async def get_processes(token: str = Depends(verify_access)):
    return system.get_filtered_process_list()

@router.post("/process/kill")
async def kill_process(payload: dict = Body(...), token: str = Depends(verify_access)):
    pid = payload.get("pid")
    return system.kill_process(pid)

@router.get("/check_admin")
async def check_admin(token: str = Depends(verify_access)):
    return {"status": "OK", "is_admin": system.check_admin()}

@router.post("/setup_master")
async def setup_master(request: Request, payload: dict = Body(...)):
    try:
        hub_pub_key = payload.get("hub_pub_key")
        if not hub_pub_key:
            raise HTTPException(status_code=400, detail="No key provided")

        # Очищаем старое (теперь db.exec переварит это без параметров)
        db.exec("DELETE FROM users WHERE ip = 'MASTER_HUB_CONFIG'")
        
        # Вставляем новое. Явно передаем кортеж.
        db.exec(
            "INSERT INTO users (token, ip) VALUES (?, ?)", 
            (str(hub_pub_key), 'MASTER_HUB_CONFIG')
        )
        
        return {"status": "OK", "message": "Linked"}
    except Exception as e:
        logger.printerr(f"Error in setup_master: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
current_lock_password: Optional[str] = None

class LockRequest(BaseModel):
    message: str = "Доступ заблокирован администратором"
    unlock_password: Optional[str] = None

@router.post("/lock/windows")
async def lock_node(req: LockRequest = Body(...), token: str = Depends(verify_access)):
    # Пишем состояние на диск
    save_lock_state(is_locked=True, message=req.message, password=req.unlock_password)
    
    payload = {
        "event": "lock_screen",
        "message": req.message,
        "has_password": req.unlock_password is not None 
    }
    
    await wsmanager.broadcast(payload)
    return {"status": "OK", "message": "Команда блокировки отправлена и сохранена"}

@router.post("/unlock/local")
async def local_unlock_node(payload: dict = Body(...)):
    state = load_lock_state()
    
    if not state.get("is_locked"):
        return {"status": "success", "message": "Terminal already unlocked"}

    stored_hash = state.get("password_hash")
    
    if stored_hash is None:
        raise HTTPException(
            status_code=403, 
            detail="Локальная разблокировка недоступна. Терминал управляется сервером."
        )
        
    input_password = payload.get("password", "")
    
    if verify_password(input_password, stored_hash):
        # Чистим стейт на диске
        save_lock_state(is_locked=False, message="", password=None)
        await wsmanager.broadcast({"event": "unlock_screen"})
        return {"status": "success"}
    
    raise HTTPException(status_code=403, detail="Неверный ключ авторизации")

@router.post("/unlock")
async def unlock_node(token: str = Depends(verify_access)):
    save_lock_state(is_locked=False, message="", password=None)
    await wsmanager.broadcast({"event": "unlock_screen"})
    return {"status": "OK", "message": "Команда разблокировки отправлена"}