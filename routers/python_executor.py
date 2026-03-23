import os
import io
import contextlib
from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from modules.auth import verify_access

router = APIRouter(prefix='/api/python', tags=['Python Executor'])

SCRIPTS_DIR = "saved_scripts"
os.makedirs(SCRIPTS_DIR, exist_ok=True)

ALLOWED_MODULES = {"math", "random", "datetime", "time"}

def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in ALLOWED_MODULES:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Модуль '{name}' запрещен.")

SAFE_BUILTINS = {
    "print": print, "range": range, "len": len, "int": int, "str": str,
    "float": float, "bool": bool, "list": list, "dict": dict, "set": set,
    "tuple": tuple, "enumerate": enumerate, "zip": zip, "min": min,
    "max": max, "sum": sum, "abs": abs, "sorted": sorted,
    "__import__": limited_import
}

def safe_exec(code: str) -> str:
    output = io.StringIO()
    env = {"__builtins__": SAFE_BUILTINS}
    try:
        with contextlib.redirect_stdout(output):
            exec(code, env, {})
        return output.getvalue()
    except Exception as e:
        return f"Ошибка выполнения: {str(e)}"

@router.post("/run")
async def run_python_code(code: str = Form(...), token: str = Depends(verify_access)):
    return {"status": "OK", "output": safe_exec(code)}

@router.get("/scripts")
async def get_all_scripts(token: str = Depends(verify_access)):
    files = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith(".py")]
    return {"status": "OK", "scripts": files}

@router.post("/scripts/save")
async def save_script(name: str = Form(...), code: str = Form(...), token: str = Depends(verify_access)):
    filename = name if name.endswith(".py") else f"{name}.py"
    path = os.path.join(SCRIPTS_DIR, os.path.basename(filename))

    # Очистка кода от лишних кареток (/r), оставляя только корректные \n
    clean_code = code.replace("\r\n", "\n").replace("\r", "\n")

    with open(path, "w", encoding="utf-8", newline='\n') as f:
        f.write(clean_code)
    return {"status": "OK"}

@router.get("/scripts/load")
async def load_script(name: str, token: str = Depends(verify_access)):
    path = os.path.join(SCRIPTS_DIR, os.path.basename(name))
    if not os.path.exists(path):
        return JSONResponse({"status": "ERROR"}, status_code=404)
    with open(path, "r", encoding="utf-8") as f:
        return {"status": "OK", "code": f.read()}
    
@router.post("/scripts/delete")
async def delete_script(name: str = Form(...), token: str = Depends(verify_access)):
    path = os.path.join(SCRIPTS_DIR, os.path.basename(name))
    if os.path.exists(path):
        os.remove(path)
        return {"status": "OK"}
    return JSONResponse({"status": "ERROR", "message": "File not found"}, status_code=404)