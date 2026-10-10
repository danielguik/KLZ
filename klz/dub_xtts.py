"""Dublagem com clonagem de voz grátis (XTTS-v2, roda em CPU). Rodar no venv py3.11:
   python klz/dub_xtts.py <pasta_projeto> <src.wav>
Lê phrases.json [{s,e,pt,en}], clona a voz do falante original, ajusta cada frase ao tempo da fala original."""
import hashlib, json, os, subprocess, sys
from pathlib import Path
os.environ["COQUI_TOS_AGREED"] = "1"  # licença CPML: uso não comercial
import numpy as np, soundfile as sf, librosa, torch, torchaudio

def _load(path, *a, **k):  # torchaudio novo exige torchcodec (CUDA); usamos soundfile
    d, sr = sf.read(path, dtype="float32", always_2d=True)
    return torch.from_numpy(d.T.copy()), sr
torchaudio.load = _load

def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True).stdout)

def main(proj, src, ref_spans):
    proj = Path(proj); out = proj / "xtts"; out.mkdir(exist_ok=True)
    y, sr = librosa.load(src, sr=22050)
    ref = np.concatenate([y[int(a*sr):int(b*sr)] for a, b in ref_spans])
    sf.write(out / "ref.wav", ref, sr)
    from TTS.api import TTS
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    ph = json.load(open(proj / "phrases.json")); info = []
    for i, p in enumerate(ph):
        nxt = ph[i+1]["s"] if i+1 < len(ph) else p["e"] + 3
        slot = max(nxt - p["s"] - 0.05, p["e"] - p["s"])
        h = hashlib.md5(f"{p.get('say', p['en'])}|{round(slot,1)}".encode()).hexdigest()[:10]; raw = str(out / f"{h}.wav"); speed = 1.0
        if os.path.exists(raw) and (out / f"{h}.json").exists():
            c = json.load(open(out / f"{h}.json")); info.append({**c, "i": i, "file": f"{h}.wav", "s": p["s"], "slot": slot, "en": p["en"]}); print(i, "cache", flush=True); continue
        for _ in range(3):
            tts.tts_to_file(text=p.get("say", p["en"]), speaker_wav=str(out / "ref.wav"), language="en", file_path=raw, speed=speed, temperature=0.6)
            d = dur(raw)
            if d <= slot * 1.03: break
            speed = min(speed * d / slot, 1.35)
        json.dump({"dur": d, "speed": round(speed, 2)}, open(out / f"{h}.json", "w"))
        info.append({"i": i, "file": f"{h}.wav", "s": p["s"], "slot": slot, "dur": d, "speed": round(speed, 2), "en": p["en"]})
        print(i, f"slot={slot:.1f} dur={d:.1f} speed={speed:.2f}", flush=True)
    json.dump(info, open(proj / "xtts_info.json", "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], [(21.7, 27.4), (31.6, 38.6), (45.6, 50.3)])
