# routers/manipulator_power.py

# Управляет состояниями питания (перезагрузка, выключение, сон) + блокировка Win+L + отмена состояний.

import asyncio, subprocess, sys

from fastapi import APIRouter
from pydantic import BaseModel

active_timers = {}

router = APIRouter(
    prefix='/api/power',
    tags=['Power Manipulator']
)

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

@router.post("/lock/screen")
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