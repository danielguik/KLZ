"""Modelo de projeto (JSON) e operações de edição — usado pela UI e pelo agente."""
import json, subprocess, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"


def new_id(prefix="l"):
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


def empty_project(name="Novo projeto"):
    return {"name": name, "width": 1280, "height": 720, "fps": 30, "assets": {}, "layers": []}


def path_of(name):
    return PROJECTS / name / "project.json"


def load(name):
    p = path_of(name)
    if not p.exists():
        save(name, empty_project(name))
    return json.loads(p.read_text())


def save(name, proj):
    p = path_of(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(proj, indent=2, ensure_ascii=False))


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    kinds = {s["codec_type"] for s in d.get("streams", [])}
    return {"duration": float(d["format"].get("duration", 0)), "has_video": "video" in kinds, "has_audio": "audio" in kinds}


def add_asset(proj, path: str, name=None):
    info = probe(path)
    aid = new_id("a")
    proj["assets"][aid] = {"path": path, "name": name or Path(path).name, **info}
    return aid


def total_duration(proj):
    return max([l["start"] + (l["out"] - l["in"]) for l in proj["layers"]] + [0])


def add_clip(proj, asset_id, start=0.0, in_=0.0, out=None):
    a = proj["assets"][asset_id]
    out = a["duration"] if out is None else min(out, a["duration"])
    kind = "video" if a["has_video"] else "audio"
    layer = {"id": new_id(), "name": a["name"], "type": kind, "asset": asset_id, "start": start,
             "in": in_, "out": out, "effects": [], "opacity": 1.0, "volume": 1.0, "x": 0, "y": 0, "scale": 1.0}
    proj["layers"].append(layer)
    return layer


def add_text(proj, text, start=0.0, duration=3.0, size=64, color="white", x="center", y="bottom"):
    layer = {"id": new_id(), "name": f"Texto: {text[:20]}", "type": "text", "text": text, "start": start,
             "in": 0, "out": duration, "size": size, "color": color, "x": x, "y": y,
             "effects": [], "opacity": 1.0, "volume": 1.0}
    proj["layers"].append(layer)
    return layer


def find(proj, layer_id):
    for l in proj["layers"]:
        if l["id"] == layer_id:
            return l
    raise KeyError(f"layer {layer_id} não existe")


def split(proj, layer_id, at):
    """Corta a camada no instante `at` (tempo da timeline)."""
    l = find(proj, layer_id)
    rel = at - l["start"]
    if not 0 < rel < l["out"] - l["in"]:
        raise ValueError("ponto de corte fora da camada")
    right = json.loads(json.dumps(l))
    right["id"] = new_id()
    right["in"] = l["in"] + rel
    right["start"] = at
    l["out"] = l["in"] + rel
    proj["layers"].append(right)
    return right
