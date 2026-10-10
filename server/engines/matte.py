"""Recorte de pessoas (para colocar texto ATRÁS delas). MediaPipe Selfie Segmentation rodando no recorte de cada pessoa
(achada pelos rostos), com limpeza da máscara e suavização no tempo. Saída: PNGs RGBA (a pessoa com transparência no fundo)."""
import json
from pathlib import Path
import numpy as np
from . import faces

def _regions(t, chains, frames, W, H, hold=1.0):
    """Região do corpo de cada pessoa visível perto do instante t (a partir do rosto: ~5 larguras de rosto de largura, ~9 de altura)."""
    if not frames: return []
    st = frames[1][0] - frames[0][0] if len(frames) > 1 else 0.08
    k = int(round(t / st)); out = []
    for c in chains:
        best, bd = None, 1e9
        for i in c["pts"]:
            d = abs(i - k)
            if d < bd: best, bd = i, d
        if best is None or bd * st > hold: continue
        x, y, w, h = c["pts"][best]["box"]
        cx = x + w / 2
        x0, x1 = cx - 2.8 * w, cx + 2.8 * w
        y0, y1 = y - 1.0 * h, y + 9.0 * h
        out.append((max(0, int(x0)), max(0, int(y0)), min(W, int(x1)), min(H, int(y1))))
    # junta regiões que se sobrepõem muito (mesma pessoa em 2 trilhas)
    merged = []
    for r in out:
        for j, m in enumerate(merged):
            ix = max(0, min(r[2], m[2]) - max(r[0], m[0])); iy = max(0, min(r[3], m[3]) - max(r[1], m[1]))
            if ix * iy > 0.5 * min((r[2] - r[0]) * (r[3] - r[1]), (m[2] - m[0]) * (m[3] - m[1])):
                merged[j] = (min(r[0], m[0]), min(r[1], m[1]), max(r[2], m[2]), max(r[3], m[3])); break
        else: merged.append(r)
    return merged

def _seg_crop(seg, img, box):
    import cv2
    x0, y0, x1, y1 = box; crop = img[y0:y1, x0:x1]
    h, w = crop.shape[:2]; s = max(h, w)
    sq = np.zeros((s, s, 3), np.uint8); sq[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w] = crop   # letterbox: não deforma a pessoa
    sq = cv2.resize(sq, (512, 512), interpolation=cv2.INTER_CUBIC)
    m = seg.process(cv2.cvtColor(sq, cv2.COLOR_BGR2RGB)).segmentation_mask
    m = cv2.resize(m, (s, s), interpolation=cv2.INTER_LINEAR)
    return m[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w]

def make_cutouts(video, out_dir, t_from, t_to, frames=None, fps=30.0, progress=lambda m: None, smooth=0.4, soft=1.6):
    """Gera out_dir/00000.png… (RGBA, mesma resolução do vídeo) para t_from..t_to. Retorna o número de quadros."""
    import cv2, mediapipe as mp
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video)); vfps = cap.get(5) or fps
    W, H = int(cap.get(3)), int(cap.get(4))
    chains = faces.tracks(frames, W, 0.08) if frames else []
    seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
    cap.set(cv2.CAP_PROP_POS_MSEC, t_from * 1000)
    n = int(round((t_to - t_from) * vfps)); prev = None; k5 = np.ones((5, 5), np.uint8); k9 = np.ones((9, 9), np.uint8)
    for i in range(n):
        ok, f = cap.read()
        if not ok: n = i; break
        t = t_from + i / vfps
        regs = _regions(t, chains, frames, W, H) or [(0, 0, W, H)]
        m = np.zeros((H, W), np.float32)
        for r in regs:
            mc = _seg_crop(seg, f, r)
            m[r[1]:r[3], r[0]:r[2]] = np.maximum(m[r[1]:r[3], r[0]:r[2]], mc)
        b = (m > 0.55).astype(np.uint8)
        b = cv2.morphologyEx(b, cv2.MORPH_OPEN, k5); b = cv2.morphologyEx(b, cv2.MORPH_CLOSE, k9)
        cnt, lab, stats, _ = cv2.connectedComponentsWithStats(b)      # só pedaços grandes (tira "tufos" soltos)
        keep = np.zeros_like(b)
        for c in range(1, cnt):
            if stats[c, cv2.CC_STAT_AREA] >= 0.004 * W * H: keep[lab == c] = 1
        mm = keep.astype(np.float32)
        if prev is not None: mm = (1 - smooth) * mm + smooth * prev    # suaviza no tempo (menos tremida na borda)
        prev = mm
        a = cv2.GaussianBlur(mm, (0, 0), soft)
        rgba = np.dstack([f, (np.clip(a, 0, 1) * 255).astype(np.uint8)])
        cv2.imwrite(str(out / f"{i:05d}.png"), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        if i % 20 == 0: progress(f"Recortando a pessoa… {i}/{n}")
    cap.release(); seg.close()
    return n
