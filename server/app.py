"""KLZ Server: API + interface web. Rode no seu computador; abra no celular pelo mesmo Wi-Fi (ou túnel)."""
import json, shutil
from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import jobs, pipeline, store
from .config import DATA, token
from .engines import translate, lipsync

token()  # cria a senha de acesso na primeira execução
app = FastAPI(title="KLZ Server")
WEB = Path(__file__).resolve().parent / "web"
PORT = {"n": 8000}

def auth(x_klz_token: str = Header(default=""), token_q: str = Query(default="", alias="token")):
    if (x_klz_token or token_q) != token():
        raise HTTPException(401, "Senha de acesso inválida.")

def proj_or_404(pid):
    try: return store.load(pid)
    except Exception: raise HTTPException(404, "Projeto não encontrado.")

@app.get("/api/ping")
def ping(): return {"ok": True, "app": "klz-server"}

@app.get("/api/capabilities", dependencies=[Depends(auth)])
def caps():
    import os
    return {"translate": translate.available(), "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")),
            "separate": True, "lipsync": "wav2lip", "whisper": os.environ.get("KLZ_WHISPER", "large-v3")}

@app.get("/api/builtin_voices", dependencies=[Depends(auth)])
def builtin_voices():
    from .engines import tts
    return tts.builtin_names()

@app.get("/api/projects", dependencies=[Depends(auth)])
def projects(): return store.list_projects()

class NewProject(BaseModel):
    name: str = "Novo projeto"

@app.post("/api/projects", dependencies=[Depends(auth)])
def new_project(b: NewProject): return store.create(b.name)

@app.delete("/api/projects/{pid}", dependencies=[Depends(auth)])
def del_project(pid: str): store.delete(pid); return {"ok": True}

@app.get("/api/projects/{pid}", dependencies=[Depends(auth)])
def get_project(pid: str):
    p = proj_or_404(pid); p["stale"] = pipeline.stale_ids(p); return p

@app.put("/api/projects/{pid}/layers", dependencies=[Depends(auth)])
def put_layers(pid: str, body: dict):
    """A interface grava aqui as camadas (timeline) e a mixagem; o resto do projeto é do servidor."""
    def fn(p):
        if "layers" in body: p["layers"] = body["layers"]
        if "durationSec" in body: p["durationSec"] = body["durationSec"]
        if "mix" in body: p["mix"] = body["mix"]
        if "cover_old_subs" in body: p["cover_old_subs"] = body["cover_old_subs"]
        if "pronounce" in body: p["pronounce"] = body["pronounce"]
    return store.update(pid, fn)["id"]

@app.post("/api/projects/{pid}/upload", dependencies=[Depends(auth)])
def upload(pid: str, file: UploadFile = File(...)):
    proj_or_404(pid); d = store.pdir(pid) / "media"
    ext = Path(file.filename or "v.mp4").suffix.lower() or ".mp4"
    dest = d / f"original{ext}"
    with dest.open("wb") as f: shutil.copyfileobj(file.file, f)
    def fn(p): p.update({"media": f"media/original{ext}", "status": "vídeo enviado", "media_name": file.filename})
    store.update(pid, fn)
    return {"ok": True, "media": f"media/original{ext}"}

class Ingest(BaseModel):
    language: str = "pt"
    n_speakers: int | None = None
    glossary: str = ""

@app.post("/api/projects/{pid}/ingest", dependencies=[Depends(auth)])
def ingest(pid: str, b: Ingest):
    p = proj_or_404(pid)
    if not p.get("media"): raise HTTPException(400, "Envie o vídeo primeiro.")
    return jobs.submit("ingest", pid, lambda pr: pipeline.ingest(pid, b.language, b.n_speakers, b.glossary, pr), "Analisar vídeo (separar voz, transcrever, identificar vozes)")

class Diar(BaseModel):
    n_speakers: int | None = None

@app.post("/api/projects/{pid}/diarize", dependencies=[Depends(auth)])
def rediarize(pid: str, b: Diar):
    proj_or_404(pid)
    return jobs.submit("diarize", pid, lambda pr: pipeline.rediarize(pid, b.n_speakers, pr), "Refazer identificação de vozes")

class Ids(BaseModel):
    ids: list[str] | None = None

@app.post("/api/projects/{pid}/translate", dependencies=[Depends(auth)])
def do_translate(pid: str, b: Ids):
    proj_or_404(pid)
    if not translate.available(): raise HTTPException(400, "Tradução automática precisa de ANTHROPIC_API_KEY no servidor. Digite a tradução à mão.")
    return jobs.submit("translate", pid, lambda pr: pipeline.translate_all(pid, b.ids, pr), "Traduzir frases")

class PhrasePatch(BaseModel):
    en: str | None = None
    pt: str | None = None
    speaker: str | None = None
    s: float | None = None
    e: float | None = None

@app.put("/api/projects/{pid}/phrases/{phid}", dependencies=[Depends(auth)])
def patch_phrase(pid: str, phid: str, b: PhrasePatch):
    """Editar a tradução NÃO gera voz sozinho: a frase fica 'desatualizada' e a tela mostra o botão Refazer voz."""
    def fn(p):
        ph = next((x for x in p["phrases"] if x["id"] == phid), None)
        if not ph: raise HTTPException(404, "Frase não encontrada.")
        for k in ("en", "pt", "speaker", "s", "e"):
            v = getattr(b, k)
            if v is not None: ph[k] = v
        pipeline.refresh_phrase_layers(p)
    p = store.update(pid, fn); p["stale"] = pipeline.stale_ids(p); return p

@app.post("/api/projects/{pid}/phrases/{phid}/merge", dependencies=[Depends(auth)])
def merge_phrase(pid: str, phid: str):
    """Junta a frase com a próxima (a fala em inglês flui melhor em trechos maiores). A voz dessa frase precisa ser refeita."""
    def fn(p):
        i = next((k for k, x in enumerate(p["phrases"]) if x["id"] == phid), None)
        if i is None or i + 1 >= len(p["phrases"]): raise HTTPException(400, "Não há frase seguinte para juntar.")
        a, b = p["phrases"][i], p["phrases"].pop(i + 1)
        a["e"] = max(a["e"], b["e"]); a["pt"] = (a["pt"] + " " + b["pt"]).strip(); a["en"] = ((a.get("en") or "") + " " + (b.get("en") or "")).strip()
        a.update({"audio": None, "voiced": None})
        pipeline.refresh_phrase_layers(p)
    p = store.update(pid, fn); p["stale"] = pipeline.stale_ids(p); return p

@app.post("/api/projects/{pid}/voice", dependencies=[Depends(auth)])
def make_voice_audio(pid: str, b: Ids):
    proj_or_404(pid)
    return jobs.submit("voice", pid, lambda pr: pipeline.voice_all(pid, b.ids, pr), "Gerar voz" + (f" ({', '.join(b.ids)})" if b.ids else " das frases pendentes"))

@app.post("/api/projects/{pid}/voices", dependencies=[Depends(auth)])
def add_voice(pid: str, name: str = Form("Nova voz"), file: UploadFile = File(...)):
    proj_or_404(pid); tmp = store.pdir(pid) / "voices" / f"_up_{file.filename}"
    with tmp.open("wb") as f: shutil.copyfileobj(file.file, f)
    try: return pipeline.make_voice(pid, name, tmp)
    finally: tmp.unlink(missing_ok=True)

class VoicePatch(BaseModel):
    name: str | None = None
    params: dict | None = None
    builtin: str | None = None   # nome de voz da biblioteca; "" = clonar da amostra

@app.put("/api/projects/{pid}/voices/{vid}", dependencies=[Depends(auth)])
def patch_voice(pid: str, vid: str, b: VoicePatch):
    def fn(p):
        v = next(x for x in p["voices"] if x["id"] == vid)
        if b.name: v["name"] = b.name
        if b.params: v["params"].update(b.params)
        if b.builtin is not None: v["builtin"] = b.builtin or None
    p = store.update(pid, fn); p["stale"] = pipeline.stale_ids(p); return p

@app.post("/api/projects/{pid}/voices/{vid}/preview", dependencies=[Depends(auth)])
def voice_preview(pid: str, vid: str, text: str = ""):
    proj_or_404(pid)
    kw = {"text": text} if text else {}
    return jobs.submit("preview", pid, lambda pr: pipeline.preview_voice(pid, vid, progress=pr, **kw), "Amostra da voz")

@app.post("/api/projects/{pid}/voices/{vid}/calibrate", dependencies=[Depends(auth)])
def voice_calibrate(pid: str, vid: str):
    proj_or_404(pid)
    return jobs.submit("calibrate", pid, lambda pr: pipeline.calibrate_voice(pid, vid, pr), "Calibrar tom da voz")

class SpeakerPatch(BaseModel):
    name: str | None = None
    voice: str | None = None

@app.put("/api/projects/{pid}/speakers/{sid}", dependencies=[Depends(auth)])
def patch_speaker(pid: str, sid: str, b: SpeakerPatch):
    def fn(p):
        s = next(x for x in p["speakers"] if x["id"] == sid)
        if b.name: s["name"] = b.name
        if b.voice: s["voice"] = b.voice
    p = store.update(pid, fn); p["stale"] = pipeline.stale_ids(p); return p

@app.post("/api/projects/{pid}/speakers", dependencies=[Depends(auth)])
def add_speaker(pid: str):
    def fn(p):
        k = len(p["speakers"]) + 1
        p["speakers"].append({"id": f"S{k}", "name": f"Falante {k}", "voice": p["voices"][0]["id"] if p["voices"] else None, "color": pipeline.COLORS[(k - 1) % 6]})
    return store.update(pid, fn)

@app.post("/api/projects/{pid}/lipsync/suggest", dependencies=[Depends(auth)])
def ls_suggest(pid: str):
    proj_or_404(pid); return jobs.submit("lipsync-suggest", pid, lambda pr: pipeline.lipsync_suggest(pid, pr), "Achar trechos com rosto falando")

class SpanPatch(BaseModel):
    enabled: bool | None = None
    strength: float | None = None
    rect: dict | None = None
    s: float | None = None
    e: float | None = None
    speaker: str | None = None

@app.put("/api/projects/{pid}/lipsync/spans/{sid}", dependencies=[Depends(auth)])
def ls_patch(pid: str, sid: str, b: SpanPatch):
    def fn(p):
        sp = next(x for x in p["lipsync"]["spans"] if x["id"] == sid)
        for k in ("enabled", "strength", "rect", "s", "e", "speaker"):
            v = getattr(b, k)
            if v is not None: sp[k] = v
        if any(getattr(b, k) is not None for k in ("rect", "s", "e", "speaker", "strength")): sp["status"] = "todo"
    return store.update(pid, fn)

@app.post("/api/projects/{pid}/lipsync/run", dependencies=[Depends(auth)])
def ls_run(pid: str, b: Ids):
    proj_or_404(pid); return jobs.submit("lipsync", pid, lambda pr: pipeline.lipsync_run(pid, b.ids, pr), "Sincronizar a boca" + (f" ({', '.join(b.ids)})" if b.ids else ""))

@app.post("/api/projects/{pid}/lipsync/compose", dependencies=[Depends(auth)])
def ls_compose(pid: str):
    proj_or_404(pid); return jobs.submit("compose", pid, lambda pr: pipeline.compose_base(pid), "Recompor vídeo com lip-sync")

class RenderReq(BaseModel):
    scale: float = 0.75
    crf: int = 18

@app.post("/api/projects/{pid}/render", dependencies=[Depends(auth)])
def do_render(pid: str, b: RenderReq):
    proj_or_404(pid)
    return jobs.submit("render", pid, lambda pr: pipeline.render(pid, b.scale, b.crf, f"http://127.0.0.1:{PORT['n']}", token(), pr), "Renderizar vídeo final")

@app.get("/api/projects/{pid}/jobs", dependencies=[Depends(auth)])
def project_jobs(pid: str): return jobs.for_project(pid)

@app.get("/api/projects/{pid}/files/{path:path}", dependencies=[Depends(auth)])
def files(pid: str, path: str):
    f = (store.pdir(pid) / path).resolve()
    if store.pdir(pid).resolve() not in f.parents or not f.is_file(): raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(f)


@app.get("/api/info", dependencies=[Depends(auth)])
def info():
    import socket
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("10.255.255.255", 1)); ips.add(s.getsockname()[0]); s.close()
    except Exception: pass
    try: ips.update(i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except Exception: pass
    return {"ips": sorted(i for i in ips if not i.startswith("127.")), "port": PORT["n"], "token": token()}

@app.get("/api/qr.svg", dependencies=[Depends(auth)])
def qr(text: str):
    import io, qrcode, qrcode.image.svg
    from fastapi.responses import Response
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf = io.BytesIO(); img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")

@app.get("/api/projects/{pid}/renders", dependencies=[Depends(auth)])
def renders(pid: str):
    d = store.pdir(pid) / "render"
    return [{"name": f.name, "size": f.stat().st_size, "time": f.stat().st_mtime} for f in sorted(d.glob("final_*.mp4"), key=lambda f: -f.stat().st_mtime)] if d.exists() else []

app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
