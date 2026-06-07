import asyncio
import logging
import sys

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, Response
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

active_timers = {}

ALLOWED_COMMANDS = ["dir", "ls", "ping", "netstat", "ipconfig", "ifconfig", "systeminfo", "whoami", "ssh"]

class ScreenshotRequest(BaseModel):
    monitor_id: int = 1

class TerminalRequest(BaseModel):
    command: str

class TimerBody(BaseModel):
    delay_seconds: int = 0  # Таймер в секундах (0 — сразу)

def an_execute_command(cmd: list):
    try:
        # Запускаем в фоне, не дожидаясь завершения (особенно важно для выключения)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Ошибка выполнения системной команды: {e}")


async def delayed_action_task(delay: int, cmd: list, action_type: str):
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        
        # Если это нативное выключение Windows, и оно дотерпело до конца,
        # системная команда всё равно отработает.
        an_execute_command(cmd)
    except asyncio.CancelledError:
        print(f"Фоновый таймер для {action_type} был успешно отменен в бэкенде.")
    finally:
        # Чистим за собой словарь при завершении или отмене
        if action_type in active_timers:
            del active_timers[action_type]

def start_timer(delay: int, cmd: list, action_type: str):
    """Хелпер для отмены старой задачи и запуска новой"""
    # Если какой-то таймер уже тикает — сбрасываем его
    cancel_internal_timers()
    
    # Если это Windows shutdown/reboot, на всякий случай шлем нативную отмену
    if sys.platform == "win32" and action_type in ["shutdown", "reboot"]:
        an_execute_command(["shutdown", "/a"])

    # Запускаем таску через asyncio в текущем event loop
    loop = asyncio.get_event_loop()
    task = loop.create_task(delayed_action_task(delay, cmd, action_type))
    active_timers["power_action"] = task

def cancel_internal_timers():
    """Остановка тасок asyncio"""
    task = active_timers.get("power_action")
    if task and not task.done():
        task.cancel()
    if "power_action" in active_timers:
        del active_timers["power_action"]

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
    
@router.post("/shutdown")
async def shutdown_node(body: TimerBody):
    if sys.platform == "win32":
        # Если задержка есть, используем нативный таймер Windows (/t) + наш внутренний для синхронизации
        cmd = ["shutdown", "/s", "/f", "/t", str(body.delay_seconds)] if body.delay_seconds > 0 else ["shutdown", "/s", "/f", "/t", "0"]
    else:
        cmd = ["sudo", "shutdown", "-h", "now"]

    start_timer(body.delay_seconds, cmd, "shutdown")
    return {"status": "OK", "message": f"Выключение запланировано через {body.delay_seconds} сек."}


@router.post("/reboot")
async def reboot_node(body: TimerBody):
    if sys.platform == "win32":
        cmd = ["shutdown", "/r", "/f", "/t", str(body.delay_seconds)] if body.delay_seconds > 0 else ["shutdown", "/r", "/f", "/t", "0"]
    else:
        cmd = ["sudo", "shutdown", "-r", "now"]

    start_timer(body.delay_seconds, cmd, "reboot")
    return {"status": "OK", "message": f"Перезагрузка запланирована через {body.delay_seconds} сек."}


@router.post("/sleep")
async def sleep_node(body: TimerBody):
    if sys.platform == "win32":
        cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"]
    else:
        cmd = ["sudo", "systemctl", "suspend"]

    start_timer(body.delay_seconds, cmd, "sleep")
    return {"status": "OK", "message": f"Переход в сон запланирован через {body.delay_seconds} сек."}


@router.post("/lock")
async def lock_node():
    # Блокировка всегда мгновенная, таймер тут не нужен
    if sys.platform == "win32":
        an_execute_command(["rundll32.exe", "user32.dll,LockWorkStation"])
    elif sys.platform == "linux":
        an_execute_command(["xdg-screensaver", "lock"])
    else:
        raise HTTPException(status_code=500, detail="Unsupported OS")
    return {"status": "OK", "message": "Сессия заблокирована"}


@router.post("/cancel")
async def cancel_actions():
    """ЭНДПОИНТ ОТМЕНЫ: тушит все запланированные таймеры"""
    # 1. Гасим внутренние async-таски (сна, выключения и т.д.)
    cancel_internal_timers()

    # 2. Если ОС Windows, принудительно шлем системную отмену (на случай, если висел нативный shutdown /t)
    if sys.platform == "win32":
        try:
            # shutdown /a вернет ошибку, если таски не было, поэтому перехватываем через Popen
            res = subprocess.run(["shutdown", "/a"], capture_output=True, text=True)
            if "Не удается отменить завершение работы системы" in res.stderr:
                pass # Игнорируем, если отменять было нечего
        except Exception as e:
            print(f"Ошибка вызова shutdown /a: {e}")

    return {"status": "OK", "message": "Все запланированные действия успешно отменены"}