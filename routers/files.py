import os
import datetime

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
import psutil
from pydantic import BaseModel

from modules.auth import verify_access

router = APIRouter(
    prefix='/api/files',
    tags=['Files']
)

@router.get("/list")
async def list_files(path: str = "C:\\", token: str = Depends(verify_access)):
    try:
        items = []
        for entry in os.scandir(path):
            info = entry.stat()
            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": f"{info.st_size / 1024:.1f} KB" if not entry.is_dir() else "-",
                "modified": datetime.datetime.fromtimestamp(info.st_mtime).strftime('%Y-%m-%d %H:%M')
            })
        # Сначала папки, потом файлы
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"status": "OK", "files": items}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
    
# Получение списка дисков
@router.get("/drives")
async def get_drives(token: str = Depends(verify_access)):
    drives = []
    for part in psutil.disk_partitions():
        if os.name == 'nt' and 'cdrom' in part.opts: continue
        drives.append({
            "device": part.device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype
        })
    return {"status": "OK", "drives": drives}

# Скачивание файла с устройства
@router.get("/download")
async def download_file(path: str, token: str = Depends(verify_access)):
    if os.path.exists(path) and os.path.isfile(path):
        return FileResponse(path, filename=os.path.basename(path))
    return {"status": "ERROR", "message": "File not found"}

# Загрузка файла на устройство
@router.post("/upload")
async def upload_file(path: str, file: UploadFile = File(...), token: str = Depends(verify_access)):
    try:
        file_path = os.path.join(path, file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        return {"status": "OK"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}    