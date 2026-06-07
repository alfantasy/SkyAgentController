import base64
import os
import datetime
import shutil
import zipfile

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
import psutil
from pydantic import BaseModel

from modules.auth import verify_access

router = APIRouter(
    prefix='/api/files',
    tags=['Files']
)

class Base64UploadPayload(BaseModel):
    path: str
    file_name: str
    content: str  # Ожидаем чистый Base64

class DeletePayload(BaseModel):
    path: str

class CreateItemPayload(BaseModel):
    path: str        # Полный путь к создаваемому элементу (включая имя)

class RenamePayload(BaseModel):
    old_path: str
    new_path: str

class SourceDestPayload(BaseModel):
    source: str
    destination: str

class ReadTextPayload(BaseModel):
    path: str

class SaveTextPayload(BaseModel):
    path: str
    content: str

class ArchivePayload(BaseModel):
    source_path: str
    zip_path: str

class UnarchivePayload(BaseModel):
    zip_path: str
    destination_path: str

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
async def download_file(request: Request, path: str, token: str = Depends(verify_access)):
    if not os.path.exists(path) or not os.path.isfile(path):
        return {"status": "ERROR", "message": "File not found"}
    
    # Проверяем, идет ли запрос через Мастер-Хаб
    is_proxied = "x-master-signature" in request.headers

    if is_proxied:
        try:
            # Читаем файл бинарно и кодируем в base64 строку для безопасного JSON-транспорта
            with open(path, "rb") as f:
                encoded_content = base64.b64encode(f.read()).decode('utf-8')
            return {
                "status": "OK",
                "content": encoded_content
            }
        except Exception as e:
            return {"status": "ERROR", "message": f"Base64 compression failed: {str(e)}"}
    else:
        # Локальный режим: отдаем стандартный бинарный FileResponse
        return FileResponse(path, filename=os.path.basename(path))
    
# Загрузка файла на устройство
@router.post("/upload")
async def upload_file(
    request: Request,
    path: str = None, # Делаем опциональными для query, т.к. при JSON они уйдут в body
    file: UploadFile = File(None), 
    token: str = Depends(verify_access)
):
    # Проверяем тип контента
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        # Режим ХАБА: парсим json-payload с Base64
        try:
            body_bytes = await request.body()
            # Превращаем в pydantic-модель вручную, т.к. сигнатура эндпоинта гибридная
            payload = Base64UploadPayload.parse_raw(body_bytes)
            
            file_path = os.path.join(payload.path, payload.file_name)
            file_data = base64.b64decode(payload.content)
            
            with open(file_path, "wb") as buffer:
                buffer.write(file_data)
                
            return {"status": "OK", "message": "Uploaded via Base64 proxy"}
        except Exception as e:
            return {"status": "ERROR", "message": f"Proxy upload failed: {str(e)}"}
            
    else:
        # ЛОКАЛЬНЫЙ РЕЖИМ: Старый добрый FormData / multipart
        if not file or not path:
            return {"status": "ERROR", "message": "Missing file or path parameter for multipart upload"}
        try:
            file_path = os.path.join(path, file.filename)
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
            return {"status": "OK", "message": "Uploaded via Local Multipart"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
        
@router.post("/delete")
async def delete_item(
    request: Request,
    path: str = None,  # Для локального режима через Query параметры
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_path = None

    # 1. Парсим путь в зависимости от транспорта (Хаб или Локалка)
    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = DeletePayload.parse_raw(body_bytes)
            target_path = payload.path
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON payload: {str(e)}"}
    else:
        # Локальный режим (Query-параметры)
        target_path = path

    # 2. Валидация пути
    if not target_path:
        return {"status": "ERROR", "message": "Missing 'path' parameter"}

    if not os.path.exists(target_path):
        return {"status": "ERROR", "message": f"Path not found: {target_path}"}

    # Защита от дурака / критическая безопасность (не дать удалить корень диска или системные папки)
    normalized = os.path.abspath(target_path)
    if normalized in ["C:\\", "D:\\", "/", "C:", "D:"] or len(normalized) < 4:
        return {"status": "ERROR", "message": "Access denied: Root directory deletion blocked"}

    # 3. Процесс удаления
    try:
        if os.path.isdir(target_path):
            # Удаляем папку со всем содержимым
            shutil.rmtree(target_path)
            return {"status": "OK", "message": f"Directory deleted successfully: {os.path.basename(target_path)}"}
        else:
            # Удаляем одиночный файл
            os.remove(target_path)
            return {"status": "OK", "message": f"File deleted successfully: {os.path.basename(target_path)}"}
            
    except PermissionError:
        return {"status": "ERROR", "message": "Permission denied: File is locked or in use"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Deletion failed: {str(e)}"}        
    
@router.post("/create_folder")
async def create_folder(
    request: Request,
    path: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_path = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = CreateItemPayload.parse_raw(body_bytes)
            target_path = payload.path
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_path = path

    if not target_path:
        return {"status": "ERROR", "message": "Missing 'path' parameter"}

    try:
        if os.path.exists(target_path):
            return {"status": "ERROR", "message": "Folder or file already exists"}
        
        os.makedirs(target_path, exist_ok=True)
        return {"status": "OK", "message": f"Folder created successfully"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Failed to create folder: {str(e)}"}

# Эндпоинт создания пустого файла
@router.post("/create_file")
async def create_file(
    request: Request,
    path: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_path = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = CreateItemPayload.parse_raw(body_bytes)
            target_path = payload.path
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_path = path

    if not target_path:
        return {"status": "ERROR", "message": "Missing 'path' parameter"}

    try:
        if os.path.exists(target_path):
            return {"status": "ERROR", "message": "File or folder already exists"}
        
        # Создаем пустой файл
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("")
            
        return {"status": "OK", "message": "File created successfully"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Failed to create file: {str(e)}"}    
    
@router.post("/rename")
async def rename_item(
    request: Request,
    old_path: str = None,
    new_path: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_old = None
    target_new = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = RenamePayload.parse_raw(body_bytes)
            target_old = payload.old_path
            target_new = payload.new_path
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_old = old_path
        target_new = new_path

    if not target_old or not target_new:
        return {"status": "ERROR", "message": "Missing 'old_path' or 'new_path' parameter"}

    try:
        if not os.path.exists(target_old):
            return {"status": "ERROR", "message": f"Source path not found: {target_old}"}
        if os.path.exists(target_new):
            return {"status": "ERROR", "message": f"Destination path already exists: {target_new}"}

        os.rename(target_old, target_new)
        return {"status": "OK", "message": "Item renamed successfully"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Rename failed: {str(e)}"}

@router.post("/copy")
async def copy_item(
    request: Request,
    source: str = None,
    destination: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_src = None
    target_dst = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = SourceDestPayload.parse_raw(body_bytes)
            target_src = payload.source
            target_dst = payload.destination
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_src = source
        target_dst = destination

    if not target_src or not target_dst:
        return {"status": "ERROR", "message": "Missing 'source' or 'destination' parameter"}

    try:
        if not os.path.exists(target_src):
            return {"status": "ERROR", "message": f"Source not found: {target_src}"}
        if os.path.exists(target_dst):
            return {"status": "ERROR", "message": f"Destination already exists: {target_dst}"}

        if os.path.isdir(target_src):
            shutil.copytree(target_src, target_dst)
        else:
            shutil.copy2(target_src, target_dst)
        return {"status": "OK", "message": "Item copied successfully"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Copy failed: {str(e)}"}

@router.post("/move")
async def move_item(
    request: Request,
    source: str = None,
    destination: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_src = None
    target_dst = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = SourceDestPayload.parse_raw(body_bytes)
            target_src = payload.source
            target_dst = payload.destination
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_src = source
        target_dst = destination

    if not target_src or not target_dst:
        return {"status": "ERROR", "message": "Missing 'source' or 'destination' parameter"}

    try:
        if not os.path.exists(target_src):
            return {"status": "ERROR", "message": f"Source not found: {target_src}"}
        if os.path.exists(target_dst):
            return {"status": "ERROR", "message": f"Destination already exists: {target_dst}"}

        shutil.move(target_src, target_dst)
        return {"status": "OK", "message": "Item moved successfully"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Move failed: {str(e)}"}

@router.get("/read_text")
async def read_text(
    request: Request,
    path: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_path = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = ReadTextPayload.parse_raw(body_bytes)
            target_path = payload.path
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_path = path

    if not target_path:
        return {"status": "ERROR", "message": "Missing 'path' parameter"}

    if not os.path.exists(target_path) or not os.path.isfile(target_path):
        return {"status": "ERROR", "message": "File not found or is a directory"}

    try:
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {"status": "OK", "content": content}
    except Exception as e:
        return {"status": "ERROR", "message": f"Read failed: {str(e)}"}

@router.post("/save_text")
async def save_text(
    request: Request,
    path: str = None,
    content: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_path = None
    target_content = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = SaveTextPayload.parse_raw(body_bytes)
            target_path = payload.path
            target_content = payload.content
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_path = path
        target_content = content

    if not target_path or target_content is None:
        return {"status": "ERROR", "message": "Missing 'path' or 'content' parameter"}

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(target_content)
        return {"status": "OK", "message": "File saved successfully"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Save failed: {str(e)}"}

@router.post("/archive")
async def archive_item(
    request: Request,
    source_path: str = None,
    zip_path: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_src = None
    target_zip = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = ArchivePayload.parse_raw(body_bytes)
            target_src = payload.source_path
            target_zip = payload.zip_path
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_src = source_path
        target_zip = zip_path

    if not target_src or not target_zip:
        return {"status": "ERROR", "message": "Missing 'source_path' or 'zip_path' parameter"}

    if not os.path.exists(target_src):
        return {"status": "ERROR", "message": f"Source path not found: {target_src}"}

    try:
        if os.path.isdir(target_src):
            # Если это папка — пакуем всё дерево рекурсивно через zipfile
            with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(target_src):
                    for file in files:
                        full_path = os.path.join(root, file)
                        # Сохраняем относительный путь, чтобы в архиве не было структуры дисков
                        arcname = os.path.relpath(full_path, start=os.path.dirname(target_src))
                        zipf.write(full_path, arcname)
        else:
            # Если одиночный файл
            with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(target_src, os.path.basename(target_src))

        return {"status": "OK", "message": f"Archive created successfully at {target_zip}"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Archiving failed: {str(e)}"}


@router.post("/unarchive")
async def unarchive_item(
    request: Request,
    zip_path: str = None,
    destination_path: str = None,
    token: str = Depends(verify_access)
):
    content_type = request.headers.get("content-type", "")
    target_zip = None
    target_dst = None

    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            payload = UnarchivePayload.parse_raw(body_bytes)
            target_zip = payload.zip_path
            target_dst = payload.destination_path
        except Exception as e:
            return {"status": "ERROR", "message": f"Failed to parse JSON: {str(e)}"}
    else:
        target_zip = zip_path
        target_dst = destination_path

    if not target_zip or not target_dst:
        return {"status": "ERROR", "message": "Missing 'zip_path' or 'destination_path' parameter"}

    if not os.path.exists(target_zip) or not os.path.isfile(target_zip):
        return {"status": "ERROR", "message": f"Zip file not found: {target_zip}"}

    try:
        os.makedirs(target_dst, exist_ok=True)
        with zipfile.ZipFile(target_zip, 'r') as zipf:
            zipf.extractall(target_dst)
        return {"status": "OK", "message": f"Archive extracted successfully to {target_dst}"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Unarchiving failed: {str(e)}"}