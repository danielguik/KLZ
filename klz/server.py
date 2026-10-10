import shutil, threading
from pathlib import Path
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import project as P, render, effects, agent, dubbing

app = FastAPI(title="KLZ Video Editor")
WEB = P.ROOT / "web"
HISTORY: dict[str, list] = {}
JOBS: dict[str, str] = {}


def _safe(name):
    if not name.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "nome inválido")
    return name


@app.get("/api/effects")
def get_effects():
    return effects.catalog_public()


@app.get("/api/projects/{name}")
def get_project(name: str):
    return P.load(_safe(name))


@app.put("/api/projects/{name}")
def put_project(name: str, proj: dict):
    P.save(_safe(name), proj)
    return {"ok": True}


@app.post("/api/projects/{name}/upload")
def upload(name: str, file: UploadFile):
    _safe(name)
    dest = P.PROJECTS / name / "media" / Path(file.filename).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    proj = P.load(name)
    aid = P.add_asset(proj, str(dest))
    P.save(name, proj)
    return {"asset_id": aid, "project": proj}


@app.get("/api/projects/{name}/media/{aid}")
def media(name: str, aid: str):
    return FileResponse(P.load(_safe(name))["assets"][aid]["path"])


@app.post("/api/projects/{name}/render")
def do_render(name: str, preview: bool = True):
    proj = P.load(_safe(name))
    out = P.PROJECTS / name / ("preview.mp4" if preview else "final.mp4")
    try:
        render.render(proj, str(out), preview)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"url": f"/api/projects/{name}/output?preview={str(preview).lower()}"}


@app.get("/api/projects/{name}/output")
def output(name: str, preview: bool = True):
    return FileResponse(P.PROJECTS / _safe(name) / ("preview.mp4" if preview else "final.mp4"))


class Chat(BaseModel):
    message: str


@app.post("/api/projects/{name}/chat")
def chat(name: str, body: Chat):
    try:
        text, HISTORY[name] = agent.chat(_safe(name), HISTORY.get(name, []), body.message)
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")
    return {"reply": text, "project": P.load(name)}


class Dub(BaseModel):
    layer_id: str


@app.post("/api/projects/{name}/dub")
def dub(name: str, body: Dub):
    """Dublagem PT->EN em segundo plano; consulte /dub/status."""
    _safe(name)
    JOBS[name] = "iniciando…"

    def work():
        try:
            proj = P.load(name)
            dubbing.dub_layer(proj, body.layer_id, name, progress=lambda m: JOBS.__setitem__(name, m))
            P.save(name, proj)
            JOBS[name] = "done"
        except Exception as e:
            JOBS[name] = f"erro: {e}"
    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}


@app.get("/api/projects/{name}/dub/status")
def dub_status(name: str):
    return {"status": JOBS.get(name, "idle")}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
