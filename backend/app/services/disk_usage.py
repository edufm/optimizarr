from __future__ import annotations

import os
import shutil
from pathlib import Path


def _mount_point(path: Path, dev: int) -> Path:
    """Sobe os ancestrais do path enquanto continuarem no mesmo device, sem depender
    de parsear /proc/mounts nem de psutil."""
    candidate = path if path.is_dir() else path.parent
    result = candidate
    for parent in candidate.parents:
        try:
            if os.stat(parent).st_dev != dev:
                break
        except OSError:
            break
        result = parent
    return result


def summarize(folders: list[dict]) -> list[dict]:
    """Agrupa pastas configuradas pelo st_dev (mesmo filesystem) e reporta uso de disco
    uma vez por grupo, deduplicando pastas que compartilham o mesmo mount."""
    groups: dict[int, dict] = {}
    for folder in folders:
        path = Path(folder["path"])
        try:
            dev = os.stat(path).st_dev
        except OSError:
            continue
        group = groups.setdefault(dev, {"dev": dev, "path": path, "folder_ids": []})
        group["folder_ids"].append(folder["id"])

    disks = []
    for group in groups.values():
        usage = shutil.disk_usage(group["path"])
        mount = _mount_point(group["path"], group["dev"])
        disks.append(
            {
                "mount": str(mount),
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "folder_ids": group["folder_ids"],
            }
        )
    return disks
