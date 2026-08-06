from __future__ import annotations

import hashlib
import json
import os
import threading

from . import config as cfg

_lock = threading.Lock()

DEFAULT_SETTINGS = {"resolution": 1080, "fps": 30, "encoder": "cpu", "quality": 24}


def folder_id_for(path: str) -> str:
    normalized = os.path.normpath(os.path.abspath(path))
    return hashlib.sha1(normalized.encode()).hexdigest()[:12]


def _ensure_dirs() -> None:
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg.CSV_DIR.mkdir(parents=True, exist_ok=True)


def _default_state() -> dict:
    return {"folders": [], "defaults": dict(DEFAULT_SETTINGS), "calibration": None}


def _write(new_state: dict) -> None:
    tmp_path = cfg.CONFIG_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(new_state, f, indent=2)
    os.replace(tmp_path, cfg.CONFIG_PATH)


def _migrate(loaded: dict) -> dict:
    """Preenche chaves novas com defaults sensatos em config.json já existentes em
    produção, sem exigir intervenção manual nem versionamento."""
    defaults = loaded.setdefault("defaults", dict(DEFAULT_SETTINGS))
    if "quality" not in defaults and "crf" in defaults:
        defaults["quality"] = defaults.pop("crf")
    defaults.setdefault("quality", DEFAULT_SETTINGS["quality"])
    defaults.setdefault("encoder", DEFAULT_SETTINGS["encoder"])
    loaded.setdefault("calibration", None)
    return loaded


def _load() -> dict:
    _ensure_dirs()
    if not cfg.CONFIG_PATH.exists():
        new_state = _default_state()
        _write(new_state)
        return new_state
    with open(cfg.CONFIG_PATH) as f:
        return _migrate(json.load(f))


def list_folders() -> list[dict]:
    with _lock:
        return _load()["folders"]


def get_folder(folder_id: str) -> dict | None:
    with _lock:
        folders = _load()["folders"]
    return next((f for f in folders if f["id"] == folder_id), None)


def add_folder(path: str) -> dict:
    normalized = os.path.normpath(os.path.abspath(path))
    new_id = folder_id_for(normalized)
    with _lock:
        current = _load()
        if any(f["id"] == new_id for f in current["folders"]):
            raise ValueError("already_exists")
        new_folder = {"id": new_id, "path": normalized}
        current["folders"].append(new_folder)
        _write(current)
        return new_folder


def remove_folder(folder_id: str) -> bool:
    with _lock:
        current = _load()
        before = len(current["folders"])
        current["folders"] = [f for f in current["folders"] if f["id"] != folder_id]
        if len(current["folders"]) == before:
            return False
        _write(current)
    (cfg.CSV_DIR / f"{folder_id}.csv").unlink(missing_ok=True)
    return True


def get_settings() -> dict:
    with _lock:
        return _load()["defaults"]


def update_settings(settings: dict) -> dict:
    with _lock:
        current = _load()
        current["defaults"] = settings
        _write(current)
        return current["defaults"]


def get_calibration() -> dict | None:
    with _lock:
        return _load()["calibration"]


def set_calibration(calibration: dict) -> dict:
    with _lock:
        current = _load()
        current["calibration"] = calibration
        _write(current)
        return current["calibration"]
