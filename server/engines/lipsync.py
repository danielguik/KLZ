"""Lip-sync editável. Cada 'trecho' (span) tem: falante, início/fim, retângulo do rosto, força (0-1), ligado/desligado.
Motor local: Wav2Lip (CPU, qualidade limitada em planos abertos). O recorte do rosto é processado e colado de volta
com borda suave, então dá para ajustar a caixa, a força ou desligar um trecho e refazer só ele."""
import json, os, subprocess, sys
from pathlib import Path
import numpy as np
from ..config import W2L_DIR

CKPT_URL = "https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth"
S3FD_URL = "https://huggingface.co/camenduru/Wav2Lip/resolve/main/face_detection/detection/sfd/s3fd.pth"

def sh(*a, **k):
    return subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True, **k)

def ensure_wav2lip(progress=lambda m: None):
    d = Path(W2L_DIR)
    if not (d / "inference.py").exists():
        progress("Baixando o Wav2Lip…")
        d.parent.mkdir(parents=True, exist_ok=True)
        sh("git", "clone", "--depth", "1", "https://github.com/Rudrabha/Wav2Lip", d)
    ck = d / "checkpoints" / "wav2lip_gan.pth"; s3 = d / "face_detection" / "detection" / "sfd" / "s3fd.pth"
    for url, f in ((CKPT_URL, ck), (S3FD_URL, s3)):
        if not f.exists() or f.stat().st_size < 10_000_000:
            progress(f"Baixando pesos ({f.name})…"); f.parent.mkdir(parents=True, exist_ok=True)
            sh("curl", "-sL", "-o", f, url)
    a = d / "audio.py"; t = a.read_text()
    if "librosa.filters.mel(hp.sample_rate" in t:  # librosa novo exige argumentos nomeados
        a.write_text(t.replace("librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,", "librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,"))
    inf = d / "inference.py"; t = inf.read_text()
    if "KLZ_PATCH" not in t:  # em vez de falhar quando um quadro não tem rosto, reaproveita a caixa anterior
        t = t.replace("\tfor rect, image in zip(predictions, images):\n\t\tif rect is None:\n\t\t\tcv2.imwrite('temp/faulty_frame.jpg', image) # check this frame where the face was not detected.\n\t\t\traise ValueError('Face not detected! Ensure the video contains a face in all the frames.')\n",
                      "\tlast_rect = None  # KLZ_PATCH\n\tfor rect, image in zip(predictions, images):\n\t\tif rect is None:\n\t\t\trect = last_rect if last_rect is not None else [0, 0, image.shape[1], image.shape[0]]\n\t\telse:\n\t\t\tlast_rect = rect\n")
        inf.write_text(t)
    return d

# ---------- escolha do rosto de cada falante (usa engines/faces.py) ----------
from .faces import probe, scan, tracks as _tracks_all

def suggest_spans(video, phrases, speakers, progress=lambda m: None, min_len=1.0, margin=0.9, step=0.2, frames=None, prefer=None):
    """Para cada falante, escolhe o rosto cuja boca mais se mexe quando ele fala e propõe trechos contínuos.
    Se o falante já tem um rosto atribuído (speaker['face_chain']), usa-o."""
    w, h, fps, total = probe(video)
    frames = frames or scan(video, step, progress)
    if not frames: return []
    st = frames[1][0] - frames[0][0] if len(frames) > 1 else step
    chains = _tracks_all(frames, w, st); times = [f[0] for f in frames]; n = len(times); spans = []
    for spk in speakers:
        act = np.array([any(p["speaker"] == spk["id"] and p["s"] <= t <= p["e"] for p in phrases) for t in times], dtype=float)
        if act.sum() < 4 or not chains: continue
        best, bs = None, -9
        pref = (prefer or {}).get(spk["id"])
        if pref:  # rostos já ligados a esta pessoa pela identificação voz+boca: usa todos eles (a pessoa pode aparecer em vários planos)
            merged = {}
            for ci in pref:
                if ci < len(chains):
                    for i, f in chains[ci]["pts"].items(): merged.setdefault(i, f)
            cand = [{"pts": merged}] if merged else []
        else: cand = chains
        for tr in cand:
            ap = np.full(n, np.nan)
            for i, f in tr["pts"].items(): ap[i] = f["mar"]
            mo = np.zeros(n); k = max(2, int(0.5 / st))
            for i in range(n):
                win = ap[max(0, i - k): i + k + 1]; win = win[~np.isnan(win)]
                mo[i] = win.std() if len(win) >= 3 else 0.0
            m = ~np.isnan(ap)
            if m.sum() < 6 or act[m].std() < 1e-6 or mo[m].std() < 1e-9: sc = -1 + 0.01 * m.sum() / n
            else: sc = float(np.corrcoef(act[m], mo[m])[0, 1]) + 0.2 * (m.sum() / n)
            if sc > bs: best, bs = tr, sc
        if best is None: continue
        pres = [i in best["pts"] for i in range(n)]
        i = 0; maxgap = int(0.8 / st)
        while i < n:
            if not pres[i]: i += 1; continue
            j = i; gap = 0
            while j + 1 < n and (pres[j + 1] or gap < maxgap):
                gap = 0 if pres[j + 1] else gap + 1; j += 1
            while j > i and not pres[j]: j -= 1
            a, b = times[i], times[j] + st
            if b - a >= min_len and act[i:j + 1].sum() >= 3:
                bx = np.array([best["pts"][k]["box"] for k in range(i, j + 1) if k in best["pts"]])
                cx = float(np.median(bx[:, 0] + bx[:, 2] / 2)); cy = float(np.median(bx[:, 1] + bx[:, 3] / 2)); fw = float(np.median(bx[:, 2]))
                spread = max(bx[:, 0].max() - bx[:, 0].min(), bx[:, 1].max() - bx[:, 1].min())
                side = max(int(fw * (1 + 2 * margin) + spread), 96)
                x0 = int(np.clip(cx - side / 2, 0, max(w - side, 0))); y0 = int(np.clip(cy - side / 2, 0, max(h - side, 0)))
                side = min(side, w - x0, h - y0)
                spans.append({"speaker": spk["id"], "s": round(a, 2), "e": round(b, 2), "rect": {"x": x0, "y": y0, "w": side, "h": side}, "face_px": int(fw), "score": round(bs, 2)})
            i = j + 1
    for k, sp in enumerate(sorted(spans, key=lambda s: s["s"])):
        small = sp["face_px"] < 80
        sp.update({"id": f"ls{k + 1}", "enabled": not small, "strength": 1.0, "status": "todo", "file": None,
                   "warn": (f"Rosto pequeno ({sp['face_px']} px de largura): o lip-sync tende a ficar borrado. Desligado por padrão; ligue se quiser testar." if small else "")})
    return sorted(spans, key=lambda s: s["s"])

# ---------- processamento de um trecho ----------
def run_span(project_dir, video, span, audio_wav, progress=lambda m: None, py=sys.executable):
    """Cria lip/<id>.mp4 (quadro inteiro, só o trecho s..e) com a boca sincronizada ao áudio dublado."""
    d = ensure_wav2lip(progress); pd = Path(project_dir) / "lip"; pd.mkdir(exist_ok=True)
    sid, s, e, r = span["id"], span["s"], span["e"], span["rect"]
    size = max(r["w"], r["h"]); size -= size % 2
    crop = pd / f"{sid}_crop.mp4"; wavp = pd / f"{sid}.wav"; out = pd / f"{sid}_lip.mp4"; final = pd / f"{sid}.mp4"
    progress(f"[{sid}] Recortando o rosto…")
    sh("ffmpeg", "-y", "-loglevel", "error", "-ss", s, "-t", e - s, "-i", video, "-vf", f"crop={size}:{size}:{r['x']}:{r['y']},scale=256:256:flags=lanczos,fps=25",
       "-an", "-c:v", "libx264", "-crf", 12, crop)
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", audio_wav, "-ss", 0, "-t", e - s, "-ar", 16000, "-ac", 1, wavp)
    progress(f"[{sid}] Sincronizando a boca (Wav2Lip, leva alguns minutos)…")
    p = subprocess.run([py, str(d / "inference.py"), "--checkpoint_path", str(d / "checkpoints" / "wav2lip_gan.pth"), "--face", str(crop), "--audio", str(wavp),
                        "--outfile", str(out), "--nosmooth", "--pads", "0", "8", "0", "0", "--face_det_batch_size", "4", "--wav2lip_batch_size", "32"],
                       cwd=d, capture_output=True, text=True)
    if p.returncode or not out.exists():
        raise RuntimeError("Wav2Lip falhou: " + (p.stderr or p.stdout)[-600:])
    progress(f"[{sid}] Colando de volta no vídeo…")
    m = max(6, size // 12); strength = float(span.get("strength", 1.0))
    # máscara com borda suave; força = opacidade da região processada
    mask = f"color=c=black:s={size}x{size}:r=25,drawbox=x={m}:y={m}:w={size - 2 * m}:h={size - 2 * m}:color=white:t=fill,gblur=sigma={m / 2},format=gray"
    fc = (f"[1:v]scale={size}:{size}:flags=lanczos,format=yuva420p[a];{mask}[m];[a][m]alphamerge,colorchannelmixer=aa={strength}[p];"
          f"[0:v][p]overlay={r['x']}:{r['y']}:shortest=1[v]")
    sh("ffmpeg", "-y", "-loglevel", "error", "-ss", s, "-t", e - s, "-i", video, "-i", out, "-filter_complex", fc, "-map", "[v]", "-an",
       "-c:v", "libx264", "-crf", 14, "-pix_fmt", "yuv420p", final)
    for f in (crop, wavp, out):
        try: f.unlink()
        except OSError: pass
    return final

def compose(video, spans, dst, fps=30):
    """Vídeo-base com os trechos de lip-sync (ligados e prontos) colocados por cima do original."""
    act = [s for s in spans if s.get("enabled") and s.get("status") == "done" and s.get("file") and Path(s["file"]).exists()]
    if not act:
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", video, "-c", "copy", "-an", dst); return dst
    ins, fc, last = [], [], "0:v"
    for i, s in enumerate(act, start=1):
        ins += ["-i", s["file"]]
        fc.append(f"[{i}:v]setpts=PTS-STARTPTS+{s['s']}/TB[o{i}]")
        fc.append(f"[{last}][o{i}]overlay=enable='between(t,{s['s']},{s['e']})':eof_action=pass[v{i}]"); last = f"v{i}"
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", video, *ins, "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-an", "-c:v", "libx264", "-crf", 14, "-pix_fmt", "yuv420p", dst)
    return dst
