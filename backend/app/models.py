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
    encoder: Literal["cpu", "nvenc"]
    quality: int = Field(ge=0, le=51)


class Calibration(BaseModel):
    target_bpp: float
    speed_factor: float
    measured_at: datetime
    encoder: Literal["cpu", "nvenc"]
    quality: int
    resolution: int
    fps: int
    sample_input: str
    sample_output: str


class SampleTestRequest(BaseModel):
    input_path: str
    output_dir: str


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
    estimated_size_bytes: int | None = None
    savings_pct: float | None = None


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
    est_size: int
    savings: float
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
    type: Literal["analyze", "optimize", "sample"]
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
