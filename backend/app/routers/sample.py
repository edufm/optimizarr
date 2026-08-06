from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from .. import state
from ..models import Calibration, JobCreated, SampleTestRequest
from ..services import job_manager

router = APIRouter(tags=["sample"])


@router.get("/calibration")
def get_calibration() -> Calibration | None:
    calibration = state.get_calibration()
    return Calibration(**calibration) if calibration else None


@router.post("/sample/test", status_code=202)
def run_sample_test(body: SampleTestRequest) -> JobCreated:
    if not os.path.isfile(body.input_path):
        raise HTTPException(400, "vídeo de entrada não encontrado")
    if not os.path.isdir(body.output_dir):
        raise HTTPException(400, "pasta de saída não encontrada")

    settings = state.get_settings()
    try:
        job = job_manager.manager.launch_sample(
            body.input_path, body.output_dir,
            resolution=settings["resolution"], fps=settings["fps"],
            encoder=settings["encoder"], quality=settings["quality"],
        )
    except job_manager.JobConflict:
        raise HTTPException(409, "já tem um teste de amostra rodando")
    return JobCreated(job_id=job.id, status=job.status)
