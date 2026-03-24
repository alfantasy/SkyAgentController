from datetime import datetime
import socket
import time
import psutil
import uvicorn
import sys
import os
import argparse # Добавляем стандартный парсер
from config import logger

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Настройка путей
logger.printinf("Initializing start of Backend...\n     | DATE: " + str(datetime.now()))
logger.printinf("Reconfigurate imports and system path of Backend.")
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

logger.printinf("Configuring routers...")    
try:
    from routers import auth, utils, files, python_executor
    logger.printinf("Paths to routers configured.")
except ImportError as e:
    logger.printerr(f"Error importing routers: {e}")
    exit(1)

app = FastAPI(openapi_url=False, docs_url=False, redoc_url=False, swagger_ui_oauth2_redirect_url=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/status")
def status():
    return {"status": "active"}

app.router.include_router(auth.router)
app.router.include_router(utils.router)
app.router.include_router(files.router)
app.router.include_router(python_executor.router)

def kill_process_on_port(port):
    """Находит и завершает процессы, занимающие порт (оптимизировано для Windows)."""
    found = False
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.status == 'LISTEN':
                pid = conn.pid
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        logger.prints(f"[OOM] Port found. Process '{proc.name()}' (PID: {pid}) is listening on port {port}.")
                        proc.terminate()
                        proc.wait(timeout=5)
                        found = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
    except psutil.AccessDenied:
        logger.printd("[OOM] Access denied while accessing net_connections.")

    if not found:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = proc.info.get('cmdline')
                if cmd and any(f'port={port}' in arg for arg in cmd):
                    logger.prints(f"[OOM] Argument found: Killing process PID {proc.info['pid']} with cmdline.")
                    proc.terminate()
                    proc.wait(timeout=5)
                    found = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    return found

def freeze_last_requirements():
    logger.printinf("Freezing last requirements on file 'requirements.txt'...")
    os.system("pip freeze > requirements.txt")
    time.sleep(1)

if __name__ == "__main__":
    # --- Секция парсинга аргументов ---
    parser = argparse.ArgumentParser(description="SkyServer Backend Settings")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="IP address to listen on")
    parser.add_argument("--port", type=int, default=7900, help="Port to listen on")
    
    args = parser.parse_args()
    
    # Теперь используем значения из аргументов (или дефолты)
    HOST = args.host
    PORT = args.port

    freeze_last_requirements()
    logger.printinf(f"Starting FastAPI server on http://{HOST}:{PORT}...")
    logger.printd("Check port availability...")

    # Проверка на занятость порта
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # Проверяем на 127.0.0.1 для надежности bind-теста в Windows
        test_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
        sock.bind((test_host, PORT))
        sock.close()
        logger.printd(f"Port {PORT} is available. Starting server...")
    except (socket.error, PermissionError):
        logger.printd(f"Port {PORT} is in use.")
        sock.close()

        logger.printd(f"[OOM] Trying to kill process on port {PORT}...")
        if kill_process_on_port(PORT):
            logger.printd("[OOM] Process on port killed. Waiting 2 seconds...")
            time.sleep(2.0)
        else:
            logger.printd("[OOM] Process not found. Waiting 2 seconds...")
            time.sleep(2.0)

    # Запуск сервера через переменные HOST и PORT
    try:
        uvicorn.run(app, host=HOST, port=PORT, reload=False)
    except Exception as e:
        logger.printerr(f"❌ Error: {e}")
        sys.exit(1)