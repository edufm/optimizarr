from __future__ import annotations

import re
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from .. import config as cfg

JobType = Literal["analyze", "optimize"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


class JobConflict(Exception):
    """Levantada quando já existe um job ativo (queued/running) para a pasta."""


@dataclass
class Job:
    id: str
    type: JobType
    folder_id: str
    file_path: str | None
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    returncode: int | None = None
    log: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    _cmd: list[str] = field(default_factory=list, repr=False)

    def log_tail(self, n: int = 200) -> list[str]:
        return list(self.log)[-n:]


class JobManager:
    """Só em memória — não sobrevive a um restart do backend, o que é aceitável já que
    não há requisito de histórico de execução (os CSVs são o único estado durável).

    Política de concorrência:
    - no máximo 1 job ativo (queued/running, analyze OU optimize) por pasta, pra não
      brigar pelo mesmo CSV/disco;
    - jobs de "optimize" são serializados globalmente (fila FIFO) — encode de verdade
      (libx265/VAAPI) é pesado, rodar dois ao mesmo tempo derruba o throughput dos dois
      sem ganho real. "analyze" (só ffprobe) não tem esse limite global.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active_by_folder: dict[str, Job] = {}
        self._optimize_running: Job | None = None
        self._optimize_queue: deque[Job] = deque()

    # --- API pública -----------------------------------------------------

    def launch_analyze(self, folder_id: str, folder_path: str) -> Job:
        cmd = [sys.executable, str(cfg.ANALYZE_SCRIPT), folder_path,
               "--csv", str(cfg.CSV_DIR / f"{folder_id}.csv")]
        with self._lock:
            if folder_id in self._active_by_folder:
                raise JobConflict(folder_id)
            job = self._new_job("analyze", folder_id, None, cmd)
            job.status = "running"
            job.started_at = _now()
            self._active_by_folder[folder_id] = job
            self._spawn(job)
        return job

    def launch_optimize(self, folder_id: str, file_path: str,
                         resolution: int, fps: int, crf: int) -> Job:
        cmd = ["bash", str(cfg.TRANSCODE_SCRIPT), file_path, "--replace",
               "--resolution", str(resolution), "--fps", str(fps), "--crf", str(crf)]
        with self._lock:
            if folder_id in self._active_by_folder:
                raise JobConflict(folder_id)
            job = self._new_job("optimize", folder_id, file_path, cmd)
            self._active_by_folder[folder_id] = job
            if self._optimize_running is None:
                job.status = "running"
                job.started_at = _now()
                self._optimize_running = job
                self._spawn(job)
            else:
                job.status = "queued"
                self._optimize_queue.append(job)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, folder_id: str | None = None, active: bool | None = None) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        if folder_id is not None:
            jobs = [j for j in jobs if j.folder_id == folder_id]
        if active is True:
            jobs = [j for j in jobs if j.status in ("queued", "running")]
        elif active is False:
            jobs = [j for j in jobs if j.status not in ("queued", "running")]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs

    def has_active_job(self, folder_id: str) -> bool:
        with self._lock:
            return folder_id in self._active_by_folder

    # --- internals ---------------------------------------------------------

    def _new_job(self, type_: JobType, folder_id: str, file_path: str | None,
                 cmd: list[str]) -> Job:
        job = Job(id=uuid4().hex, type=type_, folder_id=folder_id, file_path=file_path,
                  status="queued", created_at=_now(), _cmd=cmd)
        self._jobs[job.id] = job
        return job

    def _spawn(self, job: Job) -> None:
        threading.Thread(target=self._run, args=(job,), daemon=True).start()

    def _run(self, job: Job) -> None:
        try:
            proc = subprocess.Popen(
                job._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(cfg.REPO_ROOT),
            )
        except OSError as exc:
            job.log.append(f"Erro ao iniciar processo: {exc}")
            job.returncode = None
            job.status = "failed"
            job.finished_at = _now()
            self._on_finished(job)
            return

        # analyze-video-bloat.py imprime progresso com \r sem \n — um readline() ingênuo
        # ficaria "congelado" até o processo inteiro terminar. Lemos em chunks e
        # splitamos manualmente em \r ou \n pra cada update de progresso virar uma
        # linha de log própria.
        buf = ""
        assert proc.stdout is not None
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            *complete_lines, buf = re.split(r"[\r\n]+", buf)
            for line in complete_lines:
                if line:
                    job.log.append(line)
        if buf:
            job.log.append(buf)

        returncode = proc.wait()
        job.returncode = returncode
        job.status = "succeeded" if returncode == 0 else "failed"
        job.finished_at = _now()
        self._on_finished(job)

    def _on_finished(self, job: Job) -> None:
        with self._lock:
            if self._active_by_folder.get(job.folder_id) is job:
                del self._active_by_folder[job.folder_id]
            if job.type == "optimize" and self._optimize_running is job:
                self._optimize_running = None
                if self._optimize_queue:
                    next_job = self._optimize_queue.popleft()
                    next_job.status = "running"
                    next_job.started_at = _now()
                    self._optimize_running = next_job
                    self._spawn(next_job)


def _now() -> datetime:
    return datetime.now(timezone.utc)


manager = JobManager()
