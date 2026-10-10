"""Identificação de falantes por VOZ + BOCA (diarização audiovisual), palavra por palavra.
1) Boca: onde há rostos, a atividade da boca (desvio da abertura) indica quem fala em cada palavra.
2) Voz: das palavras com evidência visual aprende-se a voz de cada pessoa (embeddings ECAPA).
3) Decodificação (Viterbi): cada palavra recebe o falante que melhor combina voz + boca, com custo para trocar de falante.
Assim funciona também nos trechos sem rosto (closes, mãos), onde só a voz decide."""
import json
from pathlib import Path
import numpy as np, soundfile as sf
from . import faces, diar

CONF_STD = 0.030    # fala bem clara na boca: só estes trechos ensinam a voz de cada pessoa (riso/sorriso fica ~0,02)
SPEAK_STD = 0.020   # evidência fraca de fala (usada na decodificação; a voz pode desmentir)
QUIET_STD = 0.010   # abaixo disso (com o rosto visível) a pessoa está calada

def word_activity(chain, frames, ws, we, min_n=3):
    t0, t1 = ws - 0.05, max(we, ws + 0.3) + 0.05
    v = [chain["pts"][i]["mar"] for i, (t, _) in enumerate(frames) if t0 <= t <= t1 and i in chain["pts"]]
    return float(np.std(v)) if len(v) >= min_n else None

def visual_labels(words, frames, chains, thr=None):
    """Por palavra: índice da trilha (rosto) que está falando, -1 se todos os rostos visíveis estão calados, None se não dá para saber."""
    out = []
    for w in words:
        acts = [word_activity(c, frames, w["start"], w["end"]) for c in chains]
        vis = [(k, a) for k, a in enumerate(acts) if a is not None]
        if not vis: out.append(None); continue
        k, a = max(vis, key=lambda x: x[1]); others = [x[1] for x in vis if x[0] != k]
        if a >= (thr or SPEAK_STD) and all(o < 0.6 * a for o in others): out.append(k)
        elif all(a_ < QUIET_STD for _, a_ in vis): out.append(-1)
        else: out.append(None)
    return out

def embed_words(y, sr, words, enc, half=0.45):
    import torch
    E = []
    for w in words:
        c = (w["start"] + w["end"]) / 2; a = min(w["start"], c - half); b = max(w["end"], c + half)
        a = max(a, 0.0); b = min(b, len(y) / sr)
        x = torch.from_numpy(y[int(a * sr):int(b * sr)]).unsqueeze(0)
        e = enc.encode_batch(x).squeeze().detach().numpy(); E.append(e / (np.linalg.norm(e) + 1e-9))
    return np.array(E)

def run(video, wav16k, words, n_speakers=None, frames=None, cache=None, progress=lambda m: None, merge_sim=0.40, a_w=6.0, v_w=2.0, switch_cost=1.2):
    """Retorna dict: labels (um por palavra, índice do falante), n, chains (para o lip-sync) e info de depuração."""
    W = faces.probe(video)[0]
    if frames is None:
        if cache and Path(cache).exists(): frames = [(t, fs) for t, fs in json.loads(Path(cache).read_text())]
        else:
            frames = faces.scan(video, 0.08, progress)
            if cache: Path(cache).write_text(json.dumps([(t, [{"box": f["box"], "mar": f["mar"]} for f in fs]) for t, fs in frames]))
    chains = faces.tracks(frames, W, 0.08) if frames else []
    y, sr = sf.read(wav16k, dtype="float32")
    progress("Aprendendo a voz de cada pessoa…")
    enc = diar._encoder(); E = embed_words(y, sr, words, enc)
    vis_strict = visual_labels(words, frames, chains, CONF_STD) if chains else [None] * len(words)
    vis_loose = visual_labels(words, frames, chains, SPEAK_STD) if chains else [None] * len(words)
    vis = vis_strict
    # voz de cada trilha: embeddings dos TRECHOS corridos em que a boca confirma a fala (sem vazar para as palavras vizinhas)
    def runs_of(k):
        out, cur = [], []
        for i, v in enumerate(vis):
            if v == k: cur.append(i)
            else:
                if cur: out.append(cur); cur = []
        if cur: out.append(cur)
        return out
    cent = {}
    import torch
    for k in range(len(chains)):
        embs = []
        for r in runs_of(k):
            a, b = words[r[0]]["start"], words[r[-1]]["end"]
            if b - a < 0.6: a, b = (a + b) / 2 - 0.3, (a + b) / 2 + 0.3
            x = torch.from_numpy(y[int(max(a, 0) * sr):int(min(b, len(y) / sr) * sr)]).unsqueeze(0)
            e = enc.encode_batch(x).squeeze().detach().numpy(); embs.append((b - a, e / (np.linalg.norm(e) + 1e-9)))
        if embs and sum(d for d, _ in embs) >= 0.6:
            c = np.sum([d * e for d, e in embs], 0); cent[k] = c / np.linalg.norm(c)
    # Junta trilhas pela VOZ (começando pela que tem mais fala confirmada). Rosto que parece falar mas tem a mesma voz de
    # outra pessoa é só reação (riso, sorriso): entra no grupo dela e não vira um falante novo.
    dur_of = {k: sum(words[i]["end"] - words[i]["start"] for i, v in enumerate(vis) if v == k) for k in cent}
    groups = []
    for k in sorted(cent, key=lambda k: -dur_of[k]):
        c = cent[k]; best, bs = None, merge_sim
        for g in groups:
            gc = np.mean([cent[j] for j in g], 0); sim = float(c @ gc / np.linalg.norm(gc))
            if sim > bs: best, bs = g, sim
        if best is None: groups.append([k])
        else: best.append(k)
    sims = {(i, j): round(float(cent[i] @ cent[j]), 2) for i in cent for j in cent if i < j}
    if n_speakers and len(groups) != n_speakers:
        groups = groups[:n_speakers] if len(groups) > n_speakers else groups
    if not groups:  # sem evidência visual: volta para a voz só
        lab, segs, n = diar.run(wav16k, words, n_speakers, progress=progress)
        by = []
        for w in words:
            m = (w["start"] + w["end"]) / 2; by.append(next((l for l, (a, b) in zip(lab, segs) if a <= m <= b), 0))
        return {"labels": by, "n": n, "chains": [], "groups": [], "mode": "voz"}
    K = len(groups)
    C = np.array([np.mean([E[i] for k in g for i in range(len(words)) if vis[i] == k], 0) for g in groups]); C /= np.linalg.norm(C, axis=1, keepdims=True)
    # reestima uma vez usando todas as palavras já decodificadas com confiança (melhora o retrato da voz em palavras sem rosto)
    for _ in range(2):
        labels = _viterbi(words, E, C, vis_loose, groups, a_w, v_w, switch_cost)
        for k in range(K):
            idx = [i for i, l in enumerate(labels) if l == k]
            if len(idx) >= 2: C[k] = E[idx].mean(0); C[k] /= np.linalg.norm(C[k])
    labels = _viterbi(words, E, C, vis_loose, groups, a_w, v_w, switch_cost)
    return {"labels": labels, "n": K, "chains": [[int(c) for c in g] for g in groups], "mode": "voz+boca", "sims": {f"{i}-{j}": v for (i, j), v in sims.items()},
            "_chains": chains, "_frames": frames, "_vis": vis_loose}

def _viterbi(words, E, C, vis, groups, a_w, v_w, switch_cost):
    n, K = len(words), len(groups)
    chain2spk = {c: gi for gi, g in enumerate(groups) for c in g}
    em = np.zeros((n, K))
    for i in range(n):
        em[i] = a_w * (C @ E[i])
        v = vis[i]
        if v is not None and v >= 0 and v in chain2spk: em[i, chain2spk[v]] += v_w; em[i, [k for k in range(K) if k != chain2spk[v]]] -= v_w * 0.5
    dp = em[0].copy(); bp = np.zeros((n, K), dtype=int)
    for i in range(1, n):
        nd = np.empty(K)
        for k in range(K):
            cand = dp - switch_cost; cand[k] = dp[k]
            j = int(np.argmax(cand)); bp[i, k] = j; nd[k] = cand[j] + em[i, k]
        dp = nd
    path = [int(np.argmax(dp))]
    for i in range(n - 1, 0, -1): path.append(int(bp[i, path[-1]]))
    return path[::-1]
