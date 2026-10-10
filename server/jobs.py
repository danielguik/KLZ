"""Fila simples de tarefas pesadas (uma por vez), com progresso consultável pela interface."""
import threading, time, traceback, uuid, json
from queue import Queue
from .config import DATA

JOBS: dict[str, dict] = {}
_q: "Queue" = Queue()

def submit(kind: str, project: str, fn, label: str = "") -> dict:
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "kind": kind, "project": project, "label": label or kind, "status": "na fila", "progress": "", "error": None,
           "created": time.time(), "result": None}
    JOBS[jid] = job
    _q.put((job, fn))
    return job

def _worker():
    while True:
        job, fn = _q.get()
        job["status"] = "rodando"; job["started"] = time.time()
        def progress(msg, _j=job): _j["progress"] = msg
        try:
            job["result"] = fn(progress)
            job["status"] = "pronto"
        except Exception as e:  # o erro vai para a tela, não derruba o servidor
            job["status"] = "erro"; job["error"] = f"{type(e).__name__}: {e}"
            job["trace"] = traceback.format_exc()[-1500:]
        job["finished"] = time.time()
        _q.task_done()

threading.Thread(target=_worker, daemon=True).start()

def for_project(pid: str):
    return sorted([j for j in JOBS.values() if j["project"] == pid], key=lambda j: j["created"], reverse=True)[:30]
