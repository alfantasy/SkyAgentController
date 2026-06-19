import os
import json
import hashlib
from typing import Optional, Dict

LOCK_FILE = "lock_state.json"

def save_lock_state(is_locked: bool, message: str, password: Optional[str]):
    hashed_password = None
    if password:
        # Хешируем пароль перед записью на диск
        hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
        
    state = {
        "is_locked": is_locked,
        "message": message,
        "password_hash": hashed_password
    }
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def load_lock_state() -> Dict:
    if not os.path.exists(LOCK_FILE):
        return {"is_locked": False, "message": "", "password_hash": None}
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"is_locked": False, "message": "", "password_hash": None}

def verify_password(input_password: str, stored_hash: Optional[str]) -> bool:
    if not stored_hash:
        return False
    input_hash = hashlib.sha256(input_password.encode('utf-8')).hexdigest()
    return input_hash == stored_hash