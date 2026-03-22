import socket
import time
import psutil
import uvicorn
import sys
import os
import argparse # Добавляем стандартный парсер

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Настройка путей
print("Reconfigurate imports and system path to Backend.")
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from routers import auth, utils, files, python_executor
    print("Paths to routers configured.")
except ImportError as e:
    print(f"Error importing routers: {e}")

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
                        print(f"PORT FOUND: Process '{proc.name()}' (PID: {pid}) is listening on port {port}.")
                        proc.terminate()
                        proc.wait(timeout=5)
                        found = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
    except psutil.AccessDenied:
        print("Access denied while accessing net_connections.")

    if not found:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = proc.info.get('cmdline')
                if cmd and any(f'port={port}' in arg for arg in cmd):
                    print(f"Argument found: Killing process PID {proc.info['pid']} with cmdline.")
                    proc.terminate()
                    proc.wait(timeout=5)
                    found = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    return found

if __name__ == "__main__":
    # --- Секция парсинга аргументов ---
    parser = argparse.ArgumentParser(description="SkyServer Backend Settings")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="IP address to listen on")
    parser.add_argument("--port", type=int, default=7900, help="Port to listen on")
    
    args = parser.parse_args()
    
    # Теперь используем значения из аргументов (или дефолты)
    HOST = args.host
    PORT = args.port

    print(f"Starting server on http://{HOST}:{PORT}")

    # Проверка на занятость порта
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # Проверяем на 127.0.0.1 для надежности bind-теста в Windows
        test_host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
        sock.bind((test_host, PORT))
        sock.close()
        print(f"Port {PORT} is available.")
    except (socket.error, PermissionError):
        print(f"Port {PORT} is in use. Trying to find and kill the process...")
        sock.close()

        print(f"Trying to kill process on port {PORT}...")
        if kill_process_on_port(PORT):
            print("Process on port killed. Waiting 2 seconds...")
            time.sleep(2.0)
        else:
            print("Process not found. Waiting 2 seconds...")

    # Запуск сервера через переменные HOST и PORT
    try:
        uvicorn.run(app, host=HOST, port=PORT, reload=False)
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")
        sys.exit(1)