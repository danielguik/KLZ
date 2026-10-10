"""Dublagem 100% gratuita/local: segmentos PT + tradução EN -> Piper TTS -> ajuste de tempo -> áudio dublado."""
import json, subprocess, sys
from pathlib import Path

VOICE = "/tmp/t/voices/en_US-ryan-high.onnx"


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)


def synth(text, out, voice=VOICE, length_scale=1.0):
    subprocess.run([sys.executable, "-m", "piper", "-m", voice, "-f", out, "--length-scale", str(length_scale)],
                   input=text, text=True, check=True, capture_output=True)


def build(work, segs, tr, total, max_speed=1.3):
    """Gera um áudio dublado único (mono 44.1k) com cada fala no início do trecho original."""
    work = Path(work); info = []
    for i, s in enumerate(segs):
        nxt = segs[i + 1]["start"] if i + 1 < len(segs) else total
        slot = nxt - s["start"] - 0.1
        raw = str(work / f"en{i}.wav"); fit = str(work / f"en{i}_fit.wav")
        synth(tr[i]["en"], raw)
        d = dur(raw); f = max(1.0, min(d / slot, max_speed))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", f"atempo={f:.3f}", fit], check=True)
        info.append({"i": i, "start": s["start"], "raw": d, "fit": dur(fit), "slot": slot, "speed": round(f, 2), "text": tr[i]["en"]})
    ins, fl = [], []
    for k, x in enumerate(info):
        ins += ["-i", str(work / f"en{x['i']}_fit.wav")]
        ms = int(x["start"] * 1000)
        fl.append(f"[{k}:a]adelay={ms}|{ms}[a{k}]")
    fl.append("".join(f"[a{k}]" for k in range(len(info))) + f"amix=inputs={len(info)}:normalize=0[o]")
    out = str(work / "dub_en.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fl), "-map", "[o]", "-t", str(total), out], check=True)
    return out, info
