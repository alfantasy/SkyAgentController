import socket
import time
import uvicorn
import sys
import argparse # Добавляем стандартный парсер
from config import logger, app, kill_process_on_port, configurate

@app.get("/status")
def status():
    return {"status": "active"}

if __name__ == "__main__":
    # --- Секция парсинга аргументов ---
    parser = argparse.ArgumentParser(description="SkyServer Backend Settings")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="IP address to listen on")
    parser.add_argument("--port", type=int, default=7900, help="Port to listen on")
    
    args = parser.parse_args()
    
    # Теперь используем значения из аргументов (или дефолты)
    HOST = args.host
    PORT = args.port

    configurate()

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