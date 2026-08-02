from __future__ import annotations

import os

from fastapi import APIRouter

from .. import state
from ..models import DashboardOut, DiskUsageOut, FolderSummaryOut
from ..services import csv_store, disk_usage

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard() -> DashboardOut:
    folders = state.list_folders()
    disks = disk_usage.summarize(folders)

    summaries: list[FolderSummaryOut] = []
    for folder in folders:
        folder_id = folder["id"]
        label = os.path.basename(folder["path"])
        agg = csv_store.aggregate(folder_id)
        if agg is None:
            summaries.append(
                FolderSummaryOut(id=folder_id, path=folder["path"], label=label, has_csv=False)
            )
            continue
        summaries.append(
            FolderSummaryOut(
                id=folder_id, path=folder["path"], label=label, has_csv=True,
                generated_at=agg["generated_at"], file_count=agg["file_count"],
                current_size_bytes=agg["current_size_bytes"],
                estimated_size_x265_bytes=agg["estimated_size_x265_bytes"],
                savings_x265_pct=agg["savings_x265_pct"],
                estimated_size_nvenc_bytes=agg["estimated_size_nvenc_bytes"],
                savings_nvenc_pct=agg["savings_nvenc_pct"],
            )
        )

    return DashboardOut(
        disks=[DiskUsageOut(**d) for d in disks],
        folders=summaries,
    )
