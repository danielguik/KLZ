"""Gera o projeto do Studio (studio/src/projects/<nome>.json + assets em public/) a partir das frases traduzidas + áudio XTTS.
Uso: python -m klz.make_project projects/zap door [--voz original|dub]"""
import json, shutil, subprocess, sys
from pathlib import Path

KEYS = set("hopedale massachusetts império celsius snow sunshine sunny beautiful rafael fast shapes led doormaxx alucomaxx exclusive minimalist recessed handle unlocking technology available".split())
ST = Path(__file__).resolve().parent.parent / "studio"


def dur(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)


def build(w, name, voice="dub", total=64.62):
    w = Path(w); ph = json.load(open(w / "phrases.json")); info = json.load(open(w / "xtts_info.json"))
    pub = ST / "public" / name; pub.mkdir(parents=True, exist_ok=True)
    shutil.copy(w / "media/original.mp4", pub / "original.mp4")
    layers = [{"id": "vid", "name": "Vídeo original", "type": "video", "start": 0, "duration": total, "src": f"{name}/original.mp4",
               "trimStart": 0, "volume": 1.0 if voice == "original" else 0.0, "brightness": 1, "contrast": 1.05, "saturate": 1.05, "zoomPunches": []}]
    layers.append({"id": "cover", "name": "Vidro (cobre legenda antiga)", "type": "glass", "start": 0, "duration": total,
                   "enter": False, "x": 0.03, "y": 0.725, "w": 0.94, "h": 0.17, "radius": 36, "blur": 34, "tint": "rgba(10,10,14,0.5)", "borderColor": "rgba(255,255,255,0.45)"})
    words = []
    for k, (p, x) in enumerate(zip(ph, info)):
        src = w / "xtts" / x["file"]; d = dur(str(src)); rate = max(1.0, min(d / x["slot"], 1.15)) if d > x["slot"] else 1.0
        shutil.copy(src, pub / f"dub_{k}.wav")
        if voice == "dub":
            layers.append({"id": f"dub{k}", "name": f"Voz EN {k + 1}: {p['en'][:28]}", "type": "audio", "start": round(p["s"], 2), "duration": round(d / rate + 0.05, 2),
                           "src": f"{name}/dub_{k}.wav", "trimStart": 0, "volume": 1.0, "rate": round(rate, 3)})
        toks = p["en"].split(); L = sum(len(t) + 2 for t in toks); t = 0.0; D = d / rate
        for tk in toks:
            dd = D * (len(tk) + 2) / L
            words.append({"text": tk, "start": round(p["s"] + t, 3), "end": round(p["s"] + t + dd, 3), "key": tk.strip(".,:;!?'").lower().replace("'s", "") in KEYS, "p": k}); t += dd
    layers.append({"id": "cap", "name": "Legendas EN (palavra a palavra)", "type": "captions", "start": 0, "duration": total, "words": words,
                   "fontSize": 70, "y": 0.81, "color": "#ffffff", "highlight": "#ffb020", "maxChars": 17, "maxWords": 3})
    layers.append({"id": "t1", "name": "Título: local", "type": "title", "start": 0.4, "duration": 3.0, "text": "Hopedale, MA", "tag": "on site",
                   "y": 0.1, "fontSize": 110, "color": "#ffffff", "accent": "#ffb020", "accentLast": True})
    layers.append({"id": "s1", "name": "Número: temperatura", "type": "stat", "start": 7.2, "duration": 3.6, "label": "At install", "value": 14, "suffix": "°C below zero", "y": 0.1, "color": "#ffffff", "accent": "#ffb020"})
    proj = {"fps": 30, "width": 1080, "height": 1920, "durationSec": total, "layers": layers}
    (ST / "src/projects").mkdir(parents=True, exist_ok=True)
    (ST / "src/projects" / f"{name}.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1))
    write_root(proj)
    return proj


ROOT_TPL = """import React from 'react';
import {Composition} from 'remotion';
import {Reel} from './Reel';
import {Project, ProjectT} from './schema';

// GERADO por klz/make_project.py. Edite no Studio (aba Schema/JSON) e clique em Save: o Studio grava aqui.
const PROJECT: ProjectT = Project.parse(__PROJECT__);

export const Root: React.FC = () => (
  <Composition
    id="Reel"
    component={Reel}
    schema={Project}
    defaultProps={__PROJECT__}
    width={PROJECT.width}
    height={PROJECT.height}
    fps={PROJECT.fps}
    durationInFrames={Math.round(PROJECT.durationSec * PROJECT.fps)}
    calculateMetadata={({props}: {props: ProjectT}) => ({
      durationInFrames: Math.max(1, Math.round(props.durationSec * props.fps)), fps: props.fps, width: props.width, height: props.height,
    })}
  />
);
"""


def write_root(proj):
    (ST / "src/Root.tsx").write_text(ROOT_TPL.replace("__PROJECT__", json.dumps(proj, ensure_ascii=False, indent=2)))


if __name__ == "__main__":
    voice = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--voz" else "dub"
    build(sys.argv[1], sys.argv[2], voice)
