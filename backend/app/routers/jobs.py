from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import JobOut
from ..services import job_manager

router = APIRouter(tags=["jobs"])


def _to_out(job: job_manager.Job) -> JobOut:
    return JobOut(
        id=job.id,
        type=job.type,
        folder_id=job.folder_id,
        file_path=job.file_path,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        returncode=job.returncode,
        progress_pct=job.progress_pct,
        log_tail=job.log_tail(),
    )


@router.get("/jobs")
def list_jobs(folder_id: str | None = None, active: bool | None = None) -> dict:
    jobs = job_manager.manager.list(folder_id=folder_id, active=active)
    return {"jobs": [_to_out(j) for j in jobs]}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> JobOut:
    job = job_manager.manager.get(job_id)
    if job is None:
        raise HTTPException(404, "job não encontrado")
    return _to_out(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> JobOut:
    try:
        job = job_manager.manager.cancel(job_id)
    except KeyError:
        raise HTTPException(404, "job não encontrado")
    except job_manager.JobNotCancelable:
        raise HTTPException(409, "job não está mais na fila (já iniciado ou finalizado)")
    return _to_out(job)
