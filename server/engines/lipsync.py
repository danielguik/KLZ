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

# ---------- detecção de rostos e escolha do rosto de cada falante ----------
def probe(video):
    import cv2
    c = cv2.VideoCapture(str(video)); w, h, fps = int(c.get(3)), int(c.get(4)), c.get(5) or 30.0
    n = c.get(7); c.release()
    return w, h, fps, n / fps

def scan(video, step=0.2, progress=lambda m: None):
    """Lê o vídeo a cada `step` s. Candidatos (Haar) são validados pelo MediaPipe FaceMesh num recorte ampliado
    (rejeita falsos rostos como pedras) e dão a abertura da boca. Retorna [(t, [{'box':(x,y,w,h),'ap':float}])]."""
    import cv2, mediapipe as mp
    cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    fm = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=False, min_detection_confidence=0.3)
    cap = cv2.VideoCapture(str(video)); fps = cap.get(5) or 30.0; total = cap.get(7) / fps
    out = []; t = 0.0
    while t < total:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read()
        if not ok: break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY); H, W = g.shape; faces = []
        for (x, y, w, h) in cc.detectMultiScale(g, 1.1, 3, minSize=(20, 20)):
            pad = int(w * 0.6); x0, y0, x1, y1 = max(x - pad, 0), max(y - pad, 0), min(x + w + pad, W), min(y + h + pad, H)
            crop = cv2.resize(f[y0:y1, x0:x1], (256, 256), interpolation=cv2.INTER_CUBIC)
            r = fm.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            if not r.multi_face_landmarks: continue
            lm = r.multi_face_landmarks[0].landmark
            xs = np.array([q.x for q in lm]); ys = np.array([q.y for q in lm]); fh = ys.max() - ys.min()
            bx = (x0 + xs.min() * (x1 - x0), y0 + ys.min() * (y1 - y0), (xs.max() - xs.min()) * (x1 - x0), fh * (y1 - y0))
            faces.append({"box": tuple(float(v) for v in bx), "ap": float(abs(lm[13].y - lm[14].y) / fh)})
        out.append((t, faces))
        if int(t * 5) % 25 == 0: progress(f"Procurando rostos… {t:.0f}s/{total:.0f}s")
        t += step
    cap.release(); fm.close()
    return out

def _tracks(frames, W):
    """Liga rostos de amostras consecutivas em trilhas."""
    tracks = []
    for i, (t, faces) in enumerate(frames):
        used = set()
        for tr in tracks:
            last_i = max(tr["pts"])
            if i - last_i > 3: continue
            lb = tr["pts"][last_i]["box"]; lc = (lb[0] + lb[2] / 2, lb[1] + lb[3] / 2)
            best, bd = None, 0.12 * W
            for j, f in enumerate(faces):
                if j in used: continue
                b = f["box"]; d = np.hypot(b[0] + b[2] / 2 - lc[0], b[1] + b[3] / 2 - lc[1])
                if d < bd: best, bd = j, d
            if best is not None: tr["pts"][i] = faces[best]; used.add(best)
        for j, f in enumerate(faces):
            if j not in used: tracks.append({"pts": {i: f}})
    tracks = [t for t in tracks if len(t["pts"]) >= 4]
    # une pedaços da mesma pessoa: um termina e outro começa perto (até ~2 s depois, a ≤20% da largura de distância)
    def ends(t): i = max(t["pts"]); b = t["pts"][i]["box"]; return i, (b[0] + b[2] / 2, b[1] + b[3] / 2)
    def starts(t): i = min(t["pts"]); b = t["pts"][i]["box"]; return i, (b[0] + b[2] / 2, b[1] + b[3] / 2)
    chains = []
    for t in sorted(tracks, key=lambda t: min(t["pts"])):
        si, sc = starts(t); best, bd = None, 0.2 * W
        for c in chains:
            ei, ec = ends(c)
            if 0 <= si - ei <= 10 and np.hypot(sc[0] - ec[0], sc[1] - ec[1]) < bd:
                best, bd = c, np.hypot(sc[0] - ec[0], sc[1] - ec[1])
        if best is None: chains.append({"pts": dict(t["pts"])})
        else: best["pts"].update(t["pts"])
    return chains

def suggest_spans(video, phrases, speakers, progress=lambda m: None, min_len=1.0, margin=0.9, step=0.2):
    """Para cada falante, escolhe o rosto cuja boca mais se mexe quando ele fala e propõe trechos contínuos."""
    w, h, fps, total = probe(video)
    frames = scan(video, step, progress)
    if not frames: return []
    tracks = _tracks(frames, w); times = [f[0] for f in frames]; n = len(times); spans = []
    for spk in speakers:
        act = np.array([any(p["speaker"] == spk["id"] and p["s"] <= t <= p["e"] for p in phrases) for t in times], dtype=float)
        if act.sum() < 4 or not tracks: continue
        best, bs = None, -9
        for tr in tracks:
            ap = np.full(n, np.nan)
            for i, f in tr["pts"].items(): ap[i] = f["ap"]
            mo = np.zeros(n)
            for i in range(n):  # variação local da abertura da boca (≈1 s): alta quando a pessoa fala
                win = ap[max(0, i - 2): i + 3]; win = win[~np.isnan(win)]
                mo[i] = win.std() if len(win) >= 3 else 0.0
            m = ~np.isnan(ap)
            if m.sum() < 6 or act[m].std() < 1e-6 or mo[m].std() < 1e-9: sc = -1 + 0.01 * m.sum() / n
            else: sc = float(np.corrcoef(act[m], mo[m])[0, 1]) + 0.2 * (m.sum() / n)
            if sc > bs: best, bs = tr, sc
        if best is None: continue
        pres = [i in best["pts"] for i in range(n)]
        i = 0
        while i < n:
            if not pres[i]: i += 1; continue
            j = i; gap = 0
            while j + 1 < n and (pres[j + 1] or gap < 7):
                gap = 0 if pres[j + 1] else gap + 1; j += 1
            while j > i and not pres[j]: j -= 1
            a, b = times[i], times[j] + step
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
        small = sp["face_px"] < 80  # rosto pequeno no quadro: o lip-sync fica borrado e estranho
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
