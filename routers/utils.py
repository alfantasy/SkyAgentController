from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from modules.auth import verify_access

import base64, io, mss, psutil, time, platform
from PIL import Image

router = APIRouter(
    prefix='/api/utils',
    tags=['Utils']
)

class ScreenshotRequest(BaseModel):
    monitor_id: int = 1

@router.get("/ping")
async def ping_to_device():
    return {"status": "OK"}

@router.get("/monitors")
async def get_monitors(token: str = Depends(verify_access)):
    try:
        with mss.mss() as sct:
            monitors = []
            for i, m in enumerate(sct.monitors[1:], 1):
                monitors.append({
                    "id": i,
                    "width": m["width"],
                    "height": m["height"],
                    "name": f"Monitor {i} ({m['width']}x{m['height']})",
                })
            return {"status": "OK", "monitors": monitors}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@router.get("/screenshot") # Меняем на GET для простоты работы с тегом <img>
async def make_an_screenshot(
    monitor_id: int = 1, 
    quality: int = 80, 
    token: str = Depends(verify_access) # Токен будет проверяться из Query параметров
):
    try:
        with mss.mss() as sct:
            if monitor_id >= len(sct.monitors):
                raise HTTPException(status_code=404, detail="Monitor not found")
            
            monitor = sct.monitors[monitor_id]
            sct_img = sct.grab(monitor)
            
            # Конвертируем в PIL
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            
            # Оптимизируем: сохраняем в JPEG с выбранным качеством для скорости
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=quality)
            
            # Возвращаем байты напрямую с правильным media_type
            return Response(content=buffered.getvalue(), media_type="image/jpeg")
            
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

        data = {
            "cpu": {
                "model": platform.processor(),
                "usage": psutil.cpu_percent(interval=1),
                "cores": psutil.cpu_count(logical=True),
                "freq": f"{psutil.cpu_freq().current:.0f}MHz" if psutil.cpu_freq() else "N/A"
            },
            "ram": {
                "total": f"{ram.total / (1024**3):.1f}GB",
                "used": f"{ram.used / (1024**3):.1f}GB",
                "percent": ram.percent
            },
            "os": {
                "name": platform.system(),
                "release": platform.version(),
                "arch": platform.machine(),
                "uptime": f"{hours}h {minutes}m"
            }
        }
        return {"status": "OK", "data": data}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}