"""Separa voz e fundo (Demucs htdemucs, roda em CPU). Gera vocals.wav e background.wav (estéreo 44.1k)."""
import subprocess
from pathlib import Path
import numpy as np, soundfile as sf

SR = 44100

def _load(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.copy()

def run(src_media, out_dir, progress=lambda m: None):
    import torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    progress("Carregando modelo de separação…")
    model = get_model("htdemucs"); model.eval()
    wav = torch.from_numpy(_load(src_media))
    ref = wav.mean(0); mu, sd = ref.mean(), ref.std() + 1e-8
    progress("Separando voz e fundo (pode levar alguns minutos)…")
    with torch.no_grad():
        srcs = apply_model(model, ((wav - mu) / sd)[None], device="cpu", split=True, overlap=0.25, progress=False)[0]
    srcs = srcs * sd + mu
    names = model.sources
    voc = srcs[names.index("vocals")]
    bg = sum(srcs[i] for i, n in enumerate(names) if n != "vocals")
    sf.write(out_dir / "vocals.wav", voc.numpy().T, SR)
    sf.write(out_dir / "background.wav", bg.numpy().T, SR)
    return out_dir / "vocals.wav", out_dir / "background.wav"
