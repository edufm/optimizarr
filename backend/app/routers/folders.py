from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from .. import state
from ..models import FolderCreate, FolderFilesOut, FolderOut, JobCreated, CsvInfo, OptimizeRequest
from ..services import csv_store, job_manager

router = APIRouter(tags=["folders"])


def _to_out(folder: dict) -> FolderOut:
    folder_id = folder["id"]
    at = csv_store.generated_at(folder_id)
    return FolderOut(
        id=folder_id,
        path=folder["path"],
        label=os.path.basename(folder["path"]),
        csv=CsvInfo(
            exists=at is not None,
            generated_at=at,
            row_count=csv_store.row_count(folder_id) if at is not None else None,
        ),
    )


def _get_folder_or_404(folder_id: str) -> dict:
    folder = state.get_folder(folder_id)
    if folder is None:
        raise HTTPException(404, "pasta não encontrada")
    return folder


@router.get("/folders")
def list_folders() -> dict:
    return {"folders": [_to_out(f) for f in state.list_folders()]}


@router.post("/folders", status_code=201)
def create_folder(body: FolderCreate) -> FolderOut:
    path = body.path
    if not os.path.isabs(path):
        raise HTTPException(400, "path deve ser absoluto")
    if not os.path.isdir(path):
        raise HTTPException(400, "path não é um diretório existente")
    try:
        folder = state.add_folder(path)
    except ValueError:
        raise HTTPException(409, "pasta já configurada")
    return _to_out(folder)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: str) -> None:
    _get_folder_or_404(folder_id)
    if job_manager.manager.has_active_job(folder_id):
        raise HTTPException(409, "pasta tem job ativo, aguarde terminar")
    state.remove_folder(folder_id)


@router.get("/folders/{folder_id}/files")
def get_folder_files(folder_id: str) -> FolderFilesOut:
    _get_folder_or_404(folder_id)
    rows = csv_store.read_rows(folder_id)
    if rows is None:
        return FolderFilesOut(folder_id=folder_id, generated_at=None, rows=[])
    return FolderFilesOut(
        folder_id=folder_id,
        generated_at=csv_store.generated_at(folder_id),
        rows=rows,
    )


@router.post("/folders/{folder_id}/analyze", status_code=202)
def analyze_folder(folder_id: str) -> JobCreated:
    folder = _get_folder_or_404(folder_id)
    settings = state.get_settings()
    calibration = state.get_calibration()
    try:
        job = job_manager.manager.launch_analyze(
            folder_id, folder["path"],
            resolution=settings["resolution"], fps=settings["fps"],
            target_bpp=calibration["target_bpp"] if calibration else None,
            speed_factor=calibration["speed_factor"] if calibration else None,
        )
    except job_manager.JobConflict:
        raise HTTPException(409, "pasta já está sendo analisada ou tem otimização pendente")
    return JobCreated(job_id=job.id, status=job.status)


@router.post("/folders/{folder_id}/files/optimize", status_code=202)
def optimize_file(folder_id: str, body: OptimizeRequest) -> JobCreated:
    folder = _get_folder_or_404(folder_id)
    rows = csv_store.read_rows(folder_id) or []
    if not any(r["path"] == body.path for r in rows):
        raise HTTPException(400, "arquivo não encontrado na última análise desta pasta")

    folder_real = os.path.realpath(folder["path"])
    file_real = os.path.realpath(body.path)
    if not (file_real == folder_real or file_real.startswith(folder_real + os.sep)):
        raise HTTPException(400, "arquivo fora da pasta configurada")

    settings = state.get_settings()
    try:
        job = job_manager.manager.launch_optimize(
            folder_id, body.path,
            resolution=settings["resolution"], fps=settings["fps"],
            encoder=settings["encoder"], quality=settings["quality"],
        )
    except job_manager.JobConflict as exc:
        if exc.reason == "file":
            raise HTTPException(409, "esse arquivo já está na fila ou sendo otimizado")
        raise HTTPException(409, "pasta está sendo analisada agora, aguarde terminar")
    return JobCreated(job_id=job.id, status=job.status)
