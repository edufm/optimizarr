from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from .. import config as cfg

# Header real escrito por analyze-video-bloat.py (ver analyze_file()/main() no script) —
# em português e em ordem diferente dos campos internos do dict, por isso o mapa explícito.
COLUMN_MAP = {
    "arquivo": "path",
    "largura": "width",
    "altura": "height",
    "codec": "codec",
    "profile": "profile",
    "pix_fmt": "pix_fmt",
    "color_space": "color_space",
    "color_transfer": "color_transfer",
    "color_primaries": "color_primaries",
    "field_order": "field_order",
    "fps": "fps",
    "duracao_s": "duration",
    "tamanho_bytes": "size",
    "gb_por_hora": "gb_per_hour",
    "bpp": "bpp",
    "estimado_x265_bytes": "est_size_x265",
    "estimado_nvenc_bytes": "est_size_nvenc",
    "ganho_x265_pct": "savings_x265",
    "ganho_nvenc_pct": "savings_nvenc",
}

INT_FIELDS = {"width", "height", "size", "est_size_x265", "est_size_nvenc"}
FLOAT_FIELDS = {"fps", "duration", "bpp", "gb_per_hour", "savings_x265", "savings_nvenc"}


def _csv_path(folder_id: str) -> Path:
    return cfg.CSV_DIR / f"{folder_id}.csv"


def generated_at(folder_id: str) -> datetime | None:
    path = _csv_path(folder_id)
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def read_rows(folder_id: str) -> list[dict] | None:
    path = _csv_path(folder_id)
    if not path.exists():
        return None
    rows: list[dict] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row: dict = {}
            for src_key, dst_key in COLUMN_MAP.items():
                value = raw.get(src_key, "")
                if dst_key in INT_FIELDS:
                    row[dst_key] = int(float(value)) if value != "" else 0
                elif dst_key in FLOAT_FIELDS:
                    row[dst_key] = float(value) if value != "" else 0.0
                else:
                    row[dst_key] = value
            row["filename"] = os.path.basename(row["path"])
            rows.append(row)
    return rows


def row_count(folder_id: str) -> int | None:
    rows = read_rows(folder_id)
    return len(rows) if rows is not None else None


def aggregate(folder_id: str) -> dict | None:
    """Soma bruta sobre todas as linhas do CSV (não só as que passam --min-savings) —
    linhas já eficientes contribuem ~0 de economia, então o total já reflete isso."""
    rows = read_rows(folder_id)
    if rows is None:
        return None
    current_size = sum(r["size"] for r in rows)
    est_x265 = sum(r["est_size_x265"] for r in rows)
    est_nvenc = sum(r["est_size_nvenc"] for r in rows)
    savings_x265_pct = 100 * (1 - est_x265 / current_size) if current_size else 0.0
    savings_nvenc_pct = 100 * (1 - est_nvenc / current_size) if current_size else 0.0
    return {
        "generated_at": generated_at(folder_id),
        "file_count": len(rows),
        "current_size_bytes": current_size,
        "estimated_size_x265_bytes": est_x265,
        "savings_x265_pct": savings_x265_pct,
        "estimated_size_nvenc_bytes": est_nvenc,
        "savings_nvenc_pct": savings_nvenc_pct,
    }
