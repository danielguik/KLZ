"""Rostos no vídeo: detecção (Haar + validação MediaPipe FaceMesh num recorte ampliado), abertura da boca (MAR) por quadro,
rastreamento e junção de trilhas da mesma pessoa. Usado pela identificação de falantes (voz + boca) e pelo lip-sync."""
import numpy as np

def probe(video):
    import cv2
    c = cv2.VideoCapture(str(video)); w, h, fps = int(c.get(3)), int(c.get(4)), c.get(5) or 30.0
    n = c.get(7); c.release()
    return w, h, fps, n / fps

def scan(video, step=0.08, progress=lambda m: None, t_from=0.0, t_to=None):
    """Percorre o vídeo (leitura sequencial) a cada `step` s. Retorna [(t, [{'box':(x,y,w,h), 'mar':float}])].
    mar = abertura interna da boca / largura da boca (sobe quando a pessoa fala)."""
    import cv2, mediapipe as mp
    cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    fm = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=False, min_detection_confidence=0.3)
    cap = cv2.VideoCapture(str(video)); fps = cap.get(5) or 30.0; total = cap.get(7) / fps
    t_to = min(total, t_to or total); out = []; nxt = t_from; i = 0
    cap.set(cv2.CAP_PROP_POS_MSEC, t_from * 1000)
    while True:
        ok, f = cap.read()
        if not ok: break
        t = t_from + i / fps; i += 1
        if t > t_to: break
        if t + 1e-6 < nxt: continue
        nxt += step
        H, W = f.shape[:2]; sf = min(1.0, 640 / W)
        g = cv2.cvtColor(cv2.resize(f, None, fx=sf, fy=sf) if sf < 1 else f, cv2.COLOR_BGR2GRAY)
        faces = []
        for (x, y, w, h) in cc.detectMultiScale(g, 1.1, 3, minSize=(int(20 * sf), int(20 * sf))):
            x, y, w, h = x / sf, y / sf, w / sf, h / sf
            pad = int(w * 0.6); x0, y0, x1, y1 = int(max(x - pad, 0)), int(max(y - pad, 0)), int(min(x + w + pad, W)), int(min(y + h + pad, H))
            if x1 - x0 < 8 or y1 - y0 < 8: continue
            crop = cv2.resize(f[y0:y1, x0:x1], (256, 256), interpolation=cv2.INTER_CUBIC)
            r = fm.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            if not r.multi_face_landmarks: continue
            lm = r.multi_face_landmarks[0].landmark
            xs = np.array([q.x for q in lm]); ys = np.array([q.y for q in lm]); fh = ys.max() - ys.min()
            mw = abs(lm[308].x - lm[78].x) + 1e-6
            faces.append({"box": tuple(float(v) for v in (x0 + xs.min() * (x1 - x0), y0 + ys.min() * (y1 - y0), (xs.max() - xs.min()) * (x1 - x0), fh * (y1 - y0))),
                          "mar": float(abs(lm[13].y - lm[14].y) / mw)})
        out.append((round(t, 3), faces))
        if len(out) % 60 == 0: progress(f"Olhando os rostos… {t:.0f}s/{total:.0f}s")
    cap.release(); fm.close()
    return out

def tracks(frames, W, step=0.08, link_gap=0.5, join_gap=2.5):
    """Trilhas por pessoa. Primeiro liga rostos de amostras vizinhas; depois une pedaços da mesma pessoa
    (um acaba e outro começa perto, até join_gap s depois, a ≤20% da largura de distância)."""
    lg, jg = max(1, int(link_gap / step)), int(join_gap / step)
    tr = []
    for i, (t, faces) in enumerate(frames):
        used = set()
        for k in tr:
            li = max(k["pts"])
            if i - li > lg: continue
            lb = k["pts"][li]["box"]; lc = (lb[0] + lb[2] / 2, lb[1] + lb[3] / 2); best, bd = None, 0.12 * W
            for j, f in enumerate(faces):
                if j in used: continue
                b = f["box"]; d = np.hypot(b[0] + b[2] / 2 - lc[0], b[1] + b[3] / 2 - lc[1])
                if d < bd: best, bd = j, d
            if best is not None: k["pts"][i] = faces[best]; used.add(best)
        for j, f in enumerate(faces):
            if j not in used: tr.append({"pts": {i: f}})
    tr = [k for k in tr if len(k["pts"]) >= 4]
    def end(k): i = max(k["pts"]); b = k["pts"][i]["box"]; return i, (b[0] + b[2] / 2, b[1] + b[3] / 2)
    def start(k): i = min(k["pts"]); b = k["pts"][i]["box"]; return i, (b[0] + b[2] / 2, b[1] + b[3] / 2)
    chains = []
    for k in sorted(tr, key=lambda k: min(k["pts"])):
        si, sc = start(k); best, bd = None, 0.2 * W
        for c in chains:
            ei, ec = end(c); d = np.hypot(sc[0] - ec[0], sc[1] - ec[1])
            if 0 <= si - ei <= jg and d < bd: best, bd = c, d
        if best is None: chains.append({"pts": dict(k["pts"])})
        else: best["pts"].update(k["pts"])
    return chains
