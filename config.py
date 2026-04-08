from datetime import datetime
import os
import sys
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psutil

from modules.database import Database
from modules.system import System
from modules.logger import instance_logger

db = Database()
system = System()
logger = instance_logger

app = FastAPI(openapi_url=False, docs_url=False, redoc_url=False, swagger_ui_oauth2_redirect_url=False)

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

def configurate():
    logger.printinf("Initializing start of Backend...\n     | DATE: " + str(datetime.now()))
    logger.printinf("Reconfigurate imports and system path of Backend.")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    freeze_last_requirements()

    logger.printinf("Configuring routers...")    
    try:
        from routers import auth, utils, files, python_executor
        logger.printinf("Paths to routers configured.")
    except ImportError as e:
        logger.printerr(f"Error importing routers: {e}")
        exit(1)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.router.include_router(auth.router)
    app.router.include_router(utils.router)
    app.router.include_router(files.router)
    app.router.include_router(python_executor.router)    

    

