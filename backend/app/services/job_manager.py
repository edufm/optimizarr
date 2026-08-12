from __future__ import annotations

import os
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
from .. import state

JobType = Literal["analyze", "optimize", "sample"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]

_SAMPLE_KEY = "__sample__"  # folder_id sintético só pra reaproveitar o lock de 1-job-por-chave
_RESULT_RE = re.compile(r"RESULTADO bpp=([\d.]+) speed_factor=([\d.]+)")

# Linhas do bloco -progress do ffmpeg (transcode-1080p-hevc.sh e sample-test.sh) — não
# viram linha de log (senão spammam as 500 linhas do buffer numa hora de encode), só
# alimentam job.progress_pct via out_time_us/DURACAO_TOTAL.
_PROGRESS_LINE_RE = re.compile(
    r"^(frame|fps|stream_\d+_\d+_q|bitrate|total_size|out_time_us|out_time_ms|out_time|"
    r"dup_frames|drop_frames|speed|progress|DURACAO_TOTAL)="
)
_DURATION_RE = re.compile(r"^DURACAO_TOTAL=([\d.]+)$")
# nome enganoso do próprio ffmpeg: "out_time_ms" também vem em MICROsegundos (bug antigo
# mantido por compatibilidade) — por isso usamos out_time_us, que é explícito.
_OUT_TIME_US_RE = re.compile(r"^out_time_us=(-?\d+)$")


class JobConflict(Exception):
    """Levantada quando um novo job não pode ser criado por causa de outro já ativo.

    reason="folder": a pasta está sendo analisada agora (ou tem otimização pendente,
    no caso de tentar analisar). reason="file": esse arquivo específico já está na
    fila/rodando uma otimização.
    """

    def __init__(self, key: str, reason: str = "folder") -> None:
        super().__init__(key)
        self.reason = reason


class JobNotCancelable(Exception):
    """Job existe mas não está mais "queued" (já rodando ou já terminou)."""


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
    progress_pct: float | None = None
    log: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    sample_meta: dict | None = None  # só em jobs "sample": encoder/quality/resolution/fps/paths usados
    _cmd: list[str] = field(default_factory=list, repr=False)

    def log_tail(self, n: int = 200) -> list[str]:
        return list(self.log)[-n:]


class JobManager:
    """Só em memória — não sobrevive a um restart do backend, o que é aceitável já que
    não há requisito de histórico de execução (os CSVs são o único estado durável).

    Política de concorrência:
    - "analyze" (e "sample", via folder_id sintético): no máximo 1 job ativo por pasta —
      é quem escreve o CSV, então dois ao mesmo tempo na mesma pasta corromperiam a
      escrita. Também bloqueia "optimize" novo nessa pasta enquanto está rodando (não
      faz sentido trocar arquivo no meio de uma reanálise) e é bloqueado por "optimize"
      pendente na pasta (não reanalisa com arquivos ainda trocando).
    - "optimize" é serializado GLOBALMENTE (fila FIFO única pro servidor inteiro, não por
      pasta) — encode de verdade é pesado, rodar dois ao mesmo tempo (mesma pasta ou não)
      derruba o throughput dos dois sem ganho real. Como só 1 roda por vez de qualquer
      forma, várias pastas (ou vários arquivos da mesma pasta) podem enfileirar otimização
      à vontade — só o mesmo arquivo não pode ser enfileirado duas vezes.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active_by_folder: dict[str, Job] = {}  # exclusividade de analyze/sample
        self._optimize_folders: dict[str, set[str]] = {}  # folder_id -> job ids queued/running
        self._optimize_running: Job | None = None
        self._optimize_queue: deque[Job] = deque()

    # --- API pública -----------------------------------------------------

    def launch_analyze(self, folder_id: str, folder_path: str, resolution: int, fps: int,
                        target_bpp: float | None = None, speed_factor: float | None = None) -> Job:
        cmd = [sys.executable, str(cfg.ANALYZE_SCRIPT), folder_path,
               "--csv", str(cfg.CSV_DIR / f"{folder_id}.csv"),
               "--resolution", str(resolution), "--fps", str(fps)]
        # sem calibração ainda: omite as flags e deixa o script cair nos próprios defaults
        if target_bpp is not None:
            cmd += ["--target-bpp", str(target_bpp)]
        if speed_factor is not None:
            cmd += ["--speed-factor", str(speed_factor)]
        with self._lock:
            if folder_id in self._active_by_folder or self._optimize_folders.get(folder_id):
                raise JobConflict(folder_id)
            job = self._new_job("analyze", folder_id, None, cmd)
            job.status = "running"
            job.started_at = _now()
            self._active_by_folder[folder_id] = job
            self._spawn(job)
        return job

    def launch_optimize(self, folder_id: str, file_path: str,
                         resolution: int, fps: int, encoder: str, quality: int) -> Job:
        cmd = ["bash", str(cfg.TRANSCODE_SCRIPT), file_path, "--replace",
               "--resolution", str(resolution), "--fps", str(fps),
               "--encoder", encoder, "--quality", str(quality)]
        with self._lock:
            if folder_id in self._active_by_folder:
                raise JobConflict(folder_id, reason="folder")  # pasta sendo (re)analisada agora
            if any(j.type == "optimize" and j.file_path == file_path and j.status in ("queued", "running")
                   for j in self._jobs.values()):
                raise JobConflict(file_path, reason="file")  # esse arquivo já está na fila/rodando
            job = self._new_job("optimize", folder_id, file_path, cmd)
            self._optimize_folders.setdefault(folder_id, set()).add(job.id)
            if self._optimize_running is None:
                job.status = "running"
                job.started_at = _now()
                self._optimize_running = job
                self._spawn(job)
            else:
                job.status = "queued"
                self._optimize_queue.append(job)
        return job

    def launch_sample(self, input_path: str, output_dir: str,
                       resolution: int, fps: int, encoder: str, quality: int) -> Job:
        cmd = ["bash", str(cfg.SAMPLE_SCRIPT), input_path, output_dir,
               "--encoder", encoder, "--quality", str(quality),
               "--resolution", str(resolution), "--fps", str(fps)]
        with self._lock:
            if _SAMPLE_KEY in self._active_by_folder:
                raise JobConflict(_SAMPLE_KEY)
            job = self._new_job("sample", _SAMPLE_KEY, input_path, cmd)
            job.sample_meta = {
                "encoder": encoder, "quality": quality, "resolution": resolution, "fps": fps,
                "sample_input": input_path, "sample_output": output_dir,
            }
            job.status = "running"
            job.started_at = _now()
            self._active_by_folder[_SAMPLE_KEY] = job
            self._spawn(job)
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
            return folder_id in self._active_by_folder or bool(self._optimize_folders.get(folder_id))

    def cancel(self, job_id: str) -> Job:
        """Cancela um job ainda "queued" (não iniciado). Na prática só "optimize" fica
        nesse estado — "analyze"/"sample" ou começam na hora ou levantam JobConflict."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job.status != "queued":
                raise JobNotCancelable(job_id)
            self._optimize_queue = deque(j for j in self._optimize_queue if j.id != job_id)
            job.status = "cancelled"
            job.finished_at = _now()
            folder_jobs = self._optimize_folders.get(job.folder_id)
            if folder_jobs:
                folder_jobs.discard(job.id)
                if not folder_jobs:
                    del self._optimize_folders[job.folder_id]
            return job

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
                cwd=str(cfg.REPO_ROOT),
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
        #
        # Importante: usar os.read() no fd bruto, não proc.stdout.read(n) — o
        # TextIOWrapper/BufferedReader do subprocess tenta ENCHER o buffer até n
        # bytes (ou EOF) antes de retornar, então com saída esparsa (poucos KB ao
        # longo de minutos, como os echo/tee do transcode-1080p-hevc.sh) ele fica
        # bloqueado sem devolver nada até o processo inteiro terminar — o log só
        # aparecia "de uma vez" no final, nunca ao vivo. os.read() é 1 syscall só,
        # devolve o que tiver disponível na hora (semântica read1).
        buf = ""
        total_duration: float | None = None
        assert proc.stdout is not None
        fd = proc.stdout.fileno()
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            *complete_lines, buf = re.split(r"[\r\n]+", buf)
            for line in complete_lines:
                if not line:
                    continue
                duration_match = _DURATION_RE.match(line)
                if duration_match:
                    total_duration = float(duration_match.group(1)) or None
                    continue
                time_match = _OUT_TIME_US_RE.match(line)
                if time_match and total_duration:
                    elapsed = max(0, int(time_match.group(1))) / 1_000_000
                    job.progress_pct = min(100.0, elapsed / total_duration * 100)
                    continue
                if _PROGRESS_LINE_RE.match(line):
                    continue
                job.log.append(line)
        if buf and not _PROGRESS_LINE_RE.match(buf):
            job.log.append(buf)

        returncode = proc.wait()
        job.returncode = returncode
        job.status = "succeeded" if returncode == 0 else "failed"
        job.finished_at = _now()
        self._on_finished(job)

    def _on_finished(self, job: Job) -> None:
        if job.type == "sample" and job.status == "succeeded":
            self._save_calibration(job)
        with self._lock:
            if self._active_by_folder.get(job.folder_id) is job:
                del self._active_by_folder[job.folder_id]
            if job.type == "optimize":
                folder_jobs = self._optimize_folders.get(job.folder_id)
                if folder_jobs:
                    folder_jobs.discard(job.id)
                    if not folder_jobs:
                        del self._optimize_folders[job.folder_id]
                if self._optimize_running is job:
                    self._optimize_running = None
                    if self._optimize_queue:
                        next_job = self._optimize_queue.popleft()
                        next_job.status = "running"
                        next_job.started_at = _now()
                        self._optimize_running = next_job
                        self._spawn(next_job)

    def _save_calibration(self, job: Job) -> None:
        assert job.sample_meta is not None
        for line in job.log:
            match = _RESULT_RE.search(line)
            if match:
                state.set_calibration({
                    "target_bpp": float(match.group(1)),
                    "speed_factor": float(match.group(2)),
                    "measured_at": _now().isoformat(),
                    **job.sample_meta,
                })
                return
        job.log.append("Aviso: job terminou OK mas não achou a linha RESULTADO — calibração não salva.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


manager = JobManager()
