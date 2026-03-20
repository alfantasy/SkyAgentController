from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel

from modules.auth import verify_access
from config import system

import base64, io, mss, psutil, time, platform
from PIL import Image

import subprocess
import shlex

router = APIRouter(
    prefix='/api/utils',
    tags=['Utils']
)

ALLOWED_COMMANDS = ["dir", "ls", "ping", "netstat", "ipconfig", "ifconfig", "systeminfo", "whoami"]

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
        return {"status": "OK", "data": info_system_reject}
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
        return {"status": "ERROR", "message": f"Команда '{base_cmd}' запрещена службой безопасности."}

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