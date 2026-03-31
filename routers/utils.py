import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from modules.auth import verify_access
from config import system, db, logger

import base64, io, mss, psutil, time, platform
from PIL import Image

import subprocess
import shlex

router = APIRouter(
    prefix='/api/utils',
    tags=['Utils']
)

ALLOWED_COMMANDS = ["dir", "ls", "ping", "netstat", "ipconfig", "ifconfig", "systeminfo", "whoami", "ssh"]

class ScreenshotRequest(BaseModel):
    monitor_id: int = 1

class TerminalRequest(BaseModel):
    command: str

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

@router.get("/sysinfo")
async def get_sys_info(token: str = Depends(verify_access)):
    try:
        # Сбор данных о памяти
        ram = psutil.virtual_memory()
        
        # Сбор данных об аптайме
        uptime_seconds = time.time() - psutil.boot_time()
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        info_system_reject = system.info_system(hours, minutes)
        return {"status": "OK", "data": info_system_reject, "who_ami": token}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
    
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

@router.post("/setup_master")
async def setup_master(request: Request, payload: dict = Body(...)):
    try:
        client_host = request.client.host if request.client else "unknown"
        if client_host not in ("127.0.0.1", "localhost", "::1"):
            raise HTTPException(status_code=403, detail="Forbidden")

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