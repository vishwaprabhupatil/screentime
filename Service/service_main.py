# service_main.py
import time
import json
import os
from datetime import datetime

from kivy.utils import platform

try:
    from jnius import autoclass, cast
    ANDROID = (platform == "android")
except Exception:
    ANDROID = False


def debug_log(msg):
    """Simple logger."""
    print("[SERVICE]", msg)


# NEW: use the same backend as main app
try:
    from logic_backend import api_send_usage
except Exception as e:
    debug_log(f"Could not import logic_backend: {e}")
    api_send_usage = None


def get_child_config_path():
    """Where main app will store child_email & family_key."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "child_config.json")


def load_child_identity():
    """Read child email & family key written by main.py."""
    path = get_child_config_path()
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("child_email"), data.get("family_key")
    except Exception as e:
        debug_log(f"Failed to load config: {e}")
        return None, None


def get_usage_stats_last_minutes(minutes=10):
    # ... keep your existing code here unchanged ...
    ...
    return result


def send_to_server(child_email, family_key, usage_dict):
    """
    Store usage in local backend + optional debug file.
    """
    debug_log(f"Sending usage for {child_email} (key {family_key}): {len(usage_dict)} apps")

    # save into JSON "DB" so ParentScreen can see it
    if api_send_usage is not None:
        try:
            api_send_usage(child_email, usage_dict)
        except Exception as e:
            debug_log(f"api_send_usage failed: {e}")

    # still write debug file (optional)
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(base_dir, "service_usage_debug.json")
        payload = {
            "child_email": child_email,
            "family_key": family_key,
            "timestamp": datetime.now().isoformat(),
            "usage": usage_dict,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        debug_log(f"Failed to write debug file: {e}")


def main():
    debug_log("Service started")

    if not ANDROID:
        debug_log("Not running on Android, exiting.")
        return

    while True:
        child_email, family_key = load_child_identity()
        if not child_email or not family_key:
            debug_log("No child identity yet, waiting...")
        else:
            usage = get_usage_stats_last_minutes(minutes=10)
            if usage:
                send_to_server(child_email, family_key, usage)
            else:
                debug_log("No usage data this cycle.")

        time.sleep(300)


if __name__ == "__main__":
    main()
