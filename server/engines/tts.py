"""Voz com clonagem. Motor local: XTTS-v2 (grátis, CPU; licença CPML, só uso não comercial).
Motor opcional: ElevenLabs (ELEVENLABS_API_KEY) para qualidade profissional."""
import os, subprocess, tempfile
from pathlib import Path
import numpy as np, soundfile as sf

os.environ.setdefault("COQUI_TOS_AGREED", "1")
_tts = None

def _patch_torchaudio():
    import torch, torchaudio
    def _load(path, *a, **k):
        d, sr = sf.read(path, dtype="float32", always_2d=True)
        return torch.from_numpy(d.T.copy()), sr
    torchaudio.load = _load  # torchcodec não existe sem CUDA

def _xtts():
    global _tts
    if _tts is None:
        _patch_torchaudio()
        from TTS.api import TTS
        _tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    return _tts

def builtin_names():
    t = _xtts()
    try: return sorted(t.synthesizer.tts_model.speaker_manager.speaker_names)
    except Exception: return []

def default_builtin(f0=None):
    """Voz da biblioteca padrão para quando a amostra é curta demais para clonar (masculina grave por padrão)."""
    return "Claribel Dervla" if (f0 and f0 > 175) else "Damien Black"

def synth(text, ref_wav, out_wav, speed=1.0, temperature=0.6, language="en", engine="xtts", voice_id=None, builtin=None):
    if engine == "elevenlabs" and os.environ.get("ELEVENLABS_API_KEY"):
        return _eleven(text, out_wav, voice_id, speed)
    t = _xtts()
    if builtin:
        t.tts_to_file(text=text, speaker=builtin, language=language, file_path=str(out_wav), speed=float(speed), temperature=float(temperature))
    else:
        t.tts_to_file(text=text, speaker_wav=str(ref_wav), language=language, file_path=str(out_wav), speed=float(speed), temperature=float(temperature))
    return out_wav

def _eleven(text, out_wav, voice_id, speed):
    import httpx
    key = os.environ["ELEVENLABS_API_KEY"]
    r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", headers={"xi-api-key": key},
                   json={"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.4, "similarity_boost": 0.85, "speed": speed}}, timeout=300)
    r.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        f.write(r.content); f.flush()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f.name, "-ar", "24000", "-ac", "1", str(out_wav)], check=True)
    return out_wav

def duration(path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)
