"""Quantas pessoas falam e quem fala cada trecho: embeddings de voz (ECAPA/SpeechBrain) + agrupamento."""
import numpy as np, soundfile as sf

_enc = None

def _encoder():
    global _enc
    if _enc is None:
        import torch, torchaudio
        def _load(p, *a, **k):
            d, sr = sf.read(p, dtype="float32", always_2d=True)
            return torch.from_numpy(d.T.copy()), sr
        torchaudio.load = _load  # torchaudio novo exige torchcodec; usamos soundfile
        from speechbrain.inference.speaker import EncoderClassifier
        from ..config import DATA
        _enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir=str(DATA / "models" / "ecapa"), run_opts={"device": "cpu"})
    return _enc

def chunks_from_words(words, max_len=4.0, gap=0.5, min_len=1.0):
    out, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > gap or w["end"] - cur[0]["start"] > max_len):
            out.append(cur); cur = []
        cur.append(w)
    if cur: out.append(cur)
    return [(c[0]["start"], c[-1]["end"]) for c in out if c[-1]["end"] - c[0]["start"] >= min_len]

def _f0(y, sr, a, b):
    import librosa
    x = y[int(a * sr):int(b * sr)]
    f0, vf, _ = librosa.pyin(x, fmin=65, fmax=400, sr=sr, frame_length=1024)
    f = f0[vf & ~np.isnan(f0)]
    return float(np.median(f)) if len(f) > 5 else None

def run(wav16k_path, words, n_speakers=None, threshold=0.85, progress=lambda m: None):
    """Retorna (labels_por_trecho, trechos[(a,b)], n).
    Sem n_speakers: agrupa só quando as vozes são bem diferentes (limiar conservador) e junta grupos com o mesmo tom (±1,5 semitom)
    e embeddings razoavelmente parecidos. Vídeos ao ar livre/ruído deixam o mesmo falante com semelhança baixa (~0,4), por isso não usamos limiar apertado."""
    import torch
    from sklearn.cluster import AgglomerativeClustering
    y, sr = sf.read(wav16k_path, dtype="float32")
    segs = chunks_from_words(words)
    if len(segs) < 2:
        return [0] * len(segs), segs, 1
    progress("Identificando as vozes…")
    enc = _encoder()
    E = []
    for a, b in segs:
        x = torch.from_numpy(y[int(a * sr):int(b * sr)]).unsqueeze(0)
        E.append(enc.encode_batch(x).squeeze().detach().numpy())
    E = np.array(E); E /= np.linalg.norm(E, axis=1, keepdims=True)
    kw = dict(n_clusters=n_speakers) if n_speakers else dict(n_clusters=None, distance_threshold=threshold)
    lab = AgglomerativeClustering(metric="cosine", linkage="average", **kw).fit_predict(E)
    if not n_speakers and lab.max() > 0:
        f0s = [_f0(y, sr, a, b) for a, b in segs]
        changed = True
        while changed and lab.max() > 0:
            changed = False
            ks = sorted(set(lab.tolist()))
            cent = {k: E[lab == k].mean(0) for k in ks}
            fk = {k: np.median([f for f, l in zip(f0s, lab) if l == k and f]) if any(f for f, l in zip(f0s, lab) if l == k) else None for k in ks}
            for i in ks:
                for j in ks:
                    if i < j and fk[i] and fk[j] and abs(12 * np.log2(fk[i] / fk[j])) < 1.5:
                        sim = float(cent[i] @ cent[j] / (np.linalg.norm(cent[i]) * np.linalg.norm(cent[j])))
                        if sim > 0.3:
                            lab[lab == j] = i; changed = True; break
                if changed: break
        _, lab = np.unique(lab, return_inverse=True)
    return [int(l) for l in lab], segs, int(max(lab) + 1)
