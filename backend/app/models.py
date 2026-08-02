from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CsvInfo(BaseModel):
    exists: bool
    generated_at: datetime | None = None
    row_count: int | None = None


class FolderOut(BaseModel):
    id: str
    path: str
    label: str
    csv: CsvInfo


class FolderCreate(BaseModel):
    path: str


class Settings(BaseModel):
    resolution: int = Field(gt=0)
    fps: int = Field(gt=0)
    crf: int = Field(ge=0, le=51)


class DiskUsageOut(BaseModel):
    mount: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    folder_ids: list[str]


class FolderSummaryOut(BaseModel):
    id: str
    path: str
    label: str
    has_csv: bool
    generated_at: datetime | None = None
    file_count: int | None = None
    current_size_bytes: int | None = None
    estimated_size_x265_bytes: int | None = None
    savings_x265_pct: float | None = None
    estimated_size_nvenc_bytes: int | None = None
    savings_nvenc_pct: float | None = None


class DashboardOut(BaseModel):
    disks: list[DiskUsageOut]
    folders: list[FolderSummaryOut]


class FileRow(BaseModel):
    path: str
    filename: str
    codec: str
    width: int
    height: int
    fps: float
    duration: float
    size: int
    bpp: float
    est_size_x265: int
    est_size_nvenc: int
    savings_x265: float
    savings_nvenc: float
    gb_per_hour: float
    profile: str
    pix_fmt: str
    color_space: str
    color_transfer: str
    color_primaries: str
    field_order: str


class FolderFilesOut(BaseModel):
    folder_id: str
    generated_at: datetime | None = None
    rows: list[FileRow]


class OptimizeRequest(BaseModel):
    path: str


class JobOut(BaseModel):
    id: str
    type: Literal["analyze", "optimize"]
    folder_id: str
    file_path: str | None = None
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    returncode: int | None = None
    log_tail: list[str] = []


class JobCreated(BaseModel):
    job_id: str
    status: Literal["queued", "running"]
