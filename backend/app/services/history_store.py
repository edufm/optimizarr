from __future__ import annotations

import json
import threading

from .. import config as cfg

_lock = threading.Lock()


def append(entry: dict) -> None:
    """Grava uma linha de histórico de otimização (append-only, sobrevive a redeploy —
    diferente dos jobs em si, que só vivem na memória do backend)."""
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _lock, open(cfg.OPTIMIZE_HISTORY_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_recent(limit: int) -> tuple[list[dict], bool]:
    """Últimas `limit` entradas, mais recente primeiro, + se existem mais além dessas."""
    if not cfg.OPTIMIZE_HISTORY_PATH.exists():
        return [], False
    with _lock, open(cfg.OPTIMIZE_HISTORY_PATH) as f:
        lines = [line for line in f if line.strip()]
    entries = [json.loads(line) for line in lines]
    entries.reverse()
    return entries[:limit], len(entries) > limit
