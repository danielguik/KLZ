"""Análise do 'tom' de uma voz (pitch, extensão, ritmo) e ajuste de tom/volume de áudios gerados."""
import subprocess
import numpy as np

def _load(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr

def f0_stats(path):
    import librosa
    y, sr = _load(path)
    f0, vf, _ = librosa.pyin(y, fmin=65, fmax=400, sr=sr, frame_length=1024)
    f = f0[vf & ~np.isnan(f0)]
    if len(f) < 10:
        return None
    return {"f0": float(np.median(f)), "p10": float(np.percentile(f, 10)), "p90": float(np.percentile(f, 90))}

def analyze(path):
    """Retorna {f0, p10, p90, label, seconds, loudness_db}. label: grave/médio/agudo (referência para voz masculina/feminina)."""
    st = f0_stats(path)
    y, sr = _load(path)
    rms = float(20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-9))
    out = {"seconds": round(len(y) / sr, 1), "loudness_db": round(rms, 1)}
    if st:
        f = st["f0"]
        out.update({k: round(v, 1) for k, v in st.items()})
        out["label"] = "grave" if f < 110 else "médio-grave" if f < 150 else "médio" if f < 190 else "agudo"
    return out

def pitch_shift(src, dst, semitones=0.0, gain=1.0):
    """Muda o tom sem mudar a velocidade (asetrate + atempo) e ajusta o volume."""
    f = 2 ** (semitones / 12.0)
    flt = []
    if abs(semitones) > 0.01:
        flt += [f"asetrate=24000*{f:.5f}", "aresample=24000", f"atempo={1 / f:.5f}"]
    if abs(gain - 1) > 0.01:
        flt.append(f"volume={gain:.3f}")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if flt:
        cmd += ["-af", ",".join(flt)]
    subprocess.run(cmd + [str(dst)], check=True)

def match_semitones(ref_f0, out_path, limit=4.0):
    """Quantos semitons mudar o áudio gerado para ficar com o tom (f0 médio) da voz de referência."""
    st = f0_stats(out_path)
    if not st or not ref_f0:
        return 0.0
    return float(np.clip(12 * np.log2(ref_f0 / st["f0"]), -limit, limit))


def trim_silence(src, dst, pause_keep=0.18, thr="-42dB"):
    """Corta o silêncio do início/fim e encurta pausas longas (o XTTS às vezes gera segundos de silêncio)."""
    flt = (f"silenceremove=start_periods=1:start_silence=0.04:start_threshold={thr}:"
           f"stop_periods=-1:stop_duration=0.30:stop_silence={pause_keep}:stop_threshold={thr}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", flt, str(dst)], check=True)
