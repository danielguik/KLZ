"""Projetos em disco: server/data/<id>/{media,audio,voices,dub,lip,render}/ + project.json"""
import json, shutil, threading, uuid
from pathlib import Path
from .config import DATA

_lock = threading.RLock()

def pdir(pid: str) -> Path:
    if not pid.replace("-", "").replace("_", "").isalnum():
        raise ValueError("id inválido")
    return DATA / pid

def new_id(prefix="p") -> str:
    return f"{prefix}{uuid.uuid4().hex[:7]}"

def create(name: str) -> dict:
    pid = new_id()
    d = pdir(pid)
    for sub in ("media", "audio", "voices", "dub", "lip", "render"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    proj = {"id": pid, "name": name, "width": 1080, "height": 1920, "fps": 30, "durationSec": 1.0, "status": "novo",
            "speakers": [], "voices": [], "phrases": [], "lipsync": {"engine": "wav2lip", "spans": []},
            "mix": {"voice": 1.0, "background": 0.9, "original": 0.0}, "layers": []}
    save(pid, proj)
    return proj

def load(pid: str) -> dict:
    with _lock:
        return json.loads((pdir(pid) / "project.json").read_text())

def save(pid: str, proj: dict):
    with _lock:
        d = pdir(pid); d.mkdir(parents=True, exist_ok=True)
        tmp = d / "project.json.tmp"
        tmp.write_text(json.dumps(proj, ensure_ascii=False, indent=1))
        tmp.replace(d / "project.json")

def update(pid: str, fn):
    """Lê, aplica fn(proj) e grava, tudo sob lock (jobs e UI não se atropelam)."""
    with _lock:
        proj = load(pid); fn(proj); save(pid, proj); return proj

def list_projects():
    out = []
    for d in sorted(DATA.iterdir()):
        f = d / "project.json"
        if f.exists():
            p = json.loads(f.read_text()); out.append({"id": p["id"], "name": p["name"], "status": p.get("status", "")})
    return out

def delete(pid: str):
    shutil.rmtree(pdir(pid), ignore_errors=True)
