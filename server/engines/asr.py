"""Transcrição com timestamps por palavra (faster-whisper)."""
import subprocess
import numpy as np
from ..config import WHISPER

_model = None

def _audio(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

def run(path, language="pt", prompt=None, progress=lambda m: None):
    global _model
    from faster_whisper import WhisperModel
    if _model is None:
        progress(f"Carregando Whisper ({WHISPER})…")
        _model = WhisperModel(WHISPER, compute_type="int8", cpu_threads=4)
    progress("Transcrevendo a fala…")
    segs, _ = _model.transcribe(_audio(path), language=language, word_timestamps=True, vad_filter=True,
                                vad_parameters=dict(min_silence_duration_ms=300), initial_prompt=prompt)
    out = []
    for s in segs:
        words = [{"start": float(w.start), "end": float(w.end), "text": w.word.strip()} for w in (s.words or []) if w.word.strip()]
        # o Whisper às vezes cola a 1ª palavra num instante antigo, antes de uma pausa longa: corrige pelo início da palavra seguinte
        for i in range(len(words) - 1):
            if words[i + 1]["start"] - words[i]["end"] > 1.5:
                shift = words[i + 1]["start"] - 0.35
                if words[i]["start"] < shift:
                    words[i]["start"] = shift; words[i]["end"] = max(words[i]["end"], shift + 0.15)
        if words:
            out.append({"start": words[0]["start"], "end": words[-1]["end"], "text": " ".join(w["text"] for w in words), "words": words})
    return out
