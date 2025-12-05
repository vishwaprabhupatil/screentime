# logic_backend.py
import uuid
import os
import json
from datetime import datetime

# ---- File-based "DB" shared between app and service ----

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "backend_db.json")

DEFAULT_DB = {
    "parents": {},     # email -> {"password":..., "family_key": ...}
    "children": {},    # email -> {"password":..., "family_key": ...}
    "usage": {},       # child_email -> usage_dict
    "heartbeat": {}    # child_email -> timestamp string
}


def _load_db():
    """Load DB from JSON file, or create default if missing/broken."""
    if not os.path.exists(DB_PATH):
        return {k: v.copy() if isinstance(v, dict) else v for k, v in DEFAULT_DB.items()}

    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # corrupted file → reset
        return {k: v.copy() if isinstance(v, dict) else v for k, v in DEFAULT_DB.items()}

    # make sure all keys exist
    for key in DEFAULT_DB:
        if key not in data:
            data[key] = {} if isinstance(DEFAULT_DB[key], dict) else DEFAULT_DB[key]
    return data


def _save_db(db):
    """Write DB back to JSON file."""
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        print("Failed to save backend_db.json:", e)


# ---------- PARENT ----------

def api_register_parent(email, password):
    """Register parent or return existing parent’s key."""
    db = _load_db()

    if email in db["parents"]:
        return db["parents"][email]["family_key"]

    key = uuid.uuid4().hex[:8].upper()
    db["parents"][email] = {
        "password": password,
        "family_key": key,
    }

    _save_db(db)
    return key


def api_login_parent(email, password):
    """Return family key if login ok, else None."""
    db = _load_db()
    data = db["parents"].get(email)
    if not data or data["password"] != password:
        return None
    return data["family_key"]


# ---------- CHILD ----------

def api_register_child(email, password, family_key):
    """Register child and link it to the parent family key."""
    db = _load_db()

    db["children"][email] = {
        "password": password,
        "family_key": family_key,
    }

    _save_db(db)
    return True


def api_login_child(email, password):
    """Login child; return family_key if ok, else None."""
    db = _load_db()
    data = db["children"].get(email)
    if not data or data["password"] != password:
        return None
    return data["family_key"]


# ---------- USAGE + HEARTBEAT ----------

def api_send_usage(child_email, usage_dict):
    """Store latest usage + heartbeat."""
    db = _load_db()
    db["usage"][child_email] = usage_dict
    db["heartbeat"][child_email] = datetime.now().isoformat()
    _save_db(db)


def api_get_usage(parent_email, family_key):
    """Return usage for all children linked to this family key."""
    db = _load_db()
    result = {}

    for email, data in db["children"].items():
        if data["family_key"] == family_key:
            usage = db["usage"].get(email, {})
            heartbeat = db["heartbeat"].get(email, "No signal")
            result[email] = {
                "usage": usage,
                "heartbeat": heartbeat,
            }
    return result


def api_check_child_status(child_email):
    """Very rough status check based on last heartbeat."""
    db = _load_db()
    last = db["heartbeat"].get(child_email)
    if not last:
        return "NO HEARTBEAT"

    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return "NO HEARTBEAT"

    now = datetime.now()
    diff_min = (now - last_dt).total_seconds() / 60

    if diff_min > 30:
        return "NO RECENT DATA"
    return "OK"
