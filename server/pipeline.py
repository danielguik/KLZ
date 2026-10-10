"""Fluxo completo: ingestão (separar voz/fundo, transcrever, identificar falantes), tradução, vozes por falante,
refazer só frases editadas, lip-sync por trecho, montagem das camadas e render final."""
import hashlib, json, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np, soundfile as sf
from . import store
from .config import STUDIO, W2L_DIR
from .engines import asr, diar, separate, tts, voiceprint, translate, lipsync, avdiar, matte
from .engines import faces as faces_mod

COLORS = ["#4da3ff", "#ffb020", "#4cc38a", "#ff6b9a", "#b58bff", "#ff8a4c"]
KEYS = set("hopedale massachusetts celsius snow sunshine beautiful led sensor exclusive minimalist recessed handle unlocking available".split())

def sh(*a, **k):
    return subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True, **k)

def dur_of(p) -> float:
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p).stdout)

def P(pid): return store.pdir(pid)

# ---------------------------------------------------------------- frases
PT_FUNC = set("o a os as um uma uns umas de da do das dos em no na nos nas com por pra para e ou que se ao aos à às pelo pela eu tô tá é".split())

def build_phrases(segments, max_dur=6.5, protect=()):
    """Frases curtas (≈2–6 s) para dublar no tempo certo: quebra em pausas, pontuação e início de sentença (maiúscula sem ponto)."""
    prot = {w.lower().strip(".,") for w in protect}
    words = [w for s in segments for w in s["words"]]
    out, cur = [], []
    def flush():
        nonlocal cur
        if cur:
            out.append({"s": round(cur[0]["start"], 2), "e": round(cur[-1]["end"], 2), "pt": " ".join(w["text"] for w in cur), "speaker": f"S{cur[0].get('spk', 0) + 1}"})
        cur = []
    def sent_start(j):  # palavra j abre uma nova sentença (maiúscula sem ponto antes; nomes do glossário e palavras funcionais não contam)
        if j <= 0 or j >= len(words): return False
        t, prev = words[j]["text"], words[j - 1]["text"]
        return (t[:1].isupper() and not prev[:1].isupper() and not re.search(r"[.?!,;:]$", prev) and prev.lower().strip(",.") not in PT_FUNC and t.lower().strip(",.") not in prot)
    for i, w in enumerate(words):
        if cur:
            d0 = cur[-1]["end"] - cur[0]["start"]
            if w["start"] - cur[-1]["end"] > 0.6 or w.get("spk", 0) != cur[-1].get("spk", 0) or (sent_start(i) and len(cur) >= 2 and d0 >= 1.0): flush()
        cur.append(w)
        d = w["end"] - cur[0]["start"]
        near = next((words[j]["start"] for j in range(i + 1, min(i + 6, len(words))) if sent_start(j)), None)
        tail_short = near is not None and near - w["end"] < 1.3  # restaria só uma sobra curta antes da próxima sentença
        if (re.search(r"[.?!]$", w["text"]) and d >= 1.8) or (re.search(r"[,;:]$", w["text"]) and d >= 2.6 and not tail_short) or d >= max_dur + 1.5: flush()
    flush()
    # sobras muito curtas (<0.8 s) voltam para a frase anterior
    merged = []
    for p in out:
        if merged and (p["e"] - p["s"] < 0.8) and p["s"] - merged[-1]["e"] < 0.8 and p["speaker"] == merged[-1]["speaker"]:
            merged[-1]["e"] = p["e"]; merged[-1]["pt"] += " " + p["pt"]
        else: merged.append(p)
    for k, p in enumerate(merged, start=1): p["id"] = f"p{k}"
    return merged

def assign_speakers(phrases, labels, segs):
    for p in phrases:
        score = {}
        for l, (a, b) in zip(labels, segs):
            ov = min(p["e"], b) - max(p["s"], a)
            if ov > 0: score[l] = score.get(l, 0) + ov
        p["speaker"] = f"S{(max(score, key=score.get) if score else 0) + 1}"

# ---------------------------------------------------------------- vozes
def make_voice(pid, name, src_audio, speaker=None, progress=lambda m: None, force_builtin=False):
    """Cria um perfil de voz a partir de um áudio: limpa, corta ~25s de fala e analisa o tom."""
    d = P(pid); proj = store.load(pid)
    vid = f"V{len(proj['voices']) + 1}"
    ref = d / "voices" / f"{vid}.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", src_audio, "-ac", 1, "-ar", 22050, "-af",
       "silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_threshold=-45dB:stop_duration=0.4,highpass=f=70", "-t", 25, ref)
    an = voiceprint.analyze(ref)
    short = an.get("seconds", 0) < 5.0 or force_builtin
    voice = {"id": vid, "name": name, "ref": f"voices/{vid}.wav", "engine": "xtts", "analysis": an,
             "builtin": (tts.default_builtin(an.get("f0")) if short else None),
             "note": ("Amostra curta (%.1f s): clonar daria resultado ruim; usando uma voz da biblioteca com o tom ajustado ao da pessoa. Envie um áudio dela (10–25 s) para clonar." % an.get("seconds", 0)) if short else "",
             "params": {"speed": 1.0, "temperature": 0.6, "pitch": 0.0, "gain": 1.0, "auto_pitch": False}}
    def fn(p): p["voices"].append(voice)
    store.update(pid, fn)
    return voice

def speaker_reference_words(pid, spk_id, vocals16, words, k):
    """Amostra de voz do falante k: as falas dele (da trilha de voz separada, mais limpa), mais longas primeiro, até ~22 s."""
    y, sr = sf.read(vocals16, dtype="float32"); runs, cur = [], []
    for w in words:
        if w.get("spk") == k:
            if cur and w["start"] - cur[-1]["end"] > 0.4: runs.append(cur); cur = []
            cur.append(w)
        elif cur: runs.append(cur); cur = []
    if cur: runs.append(cur)
    runs = sorted(runs, key=lambda r: r[-1]["end"] - r[0]["start"], reverse=True)
    parts, tot = [], 0.0
    for r in runs:
        a, b = max(r[0]["start"] - 0.05, 0), r[-1]["end"] + 0.05
        parts.append(y[int(a * sr):int(b * sr)]); tot += b - a
        if tot >= 22: break
    out = P(pid) / "voices" / f"_ref_{spk_id}.wav"
    sf.write(out, np.concatenate(parts) if parts else y[: sr * 5], sr)
    return out, tot

def speaker_reference(pid, spk_id, vocals16, labels, segs, speaker_idx):
    """Junta até ~22s de fala do falante (da trilha de voz já separada, mais limpa) como amostra para clonar."""
    y, sr = sf.read(vocals16, dtype="float32")
    picks = sorted([(b - a, a, b) for l, (a, b) in zip(labels, segs) if l == speaker_idx], reverse=True)
    parts, tot = [], 0.0
    for d, a, b in picks:
        parts.append(y[int(a * sr):int(b * sr)]); tot += d
        if tot >= 22: break
    out = P(pid) / "voices" / f"_ref_{spk_id}.wav"
    sf.write(out, np.concatenate(parts) if parts else y[: sr * 10], sr)
    return out

# ---------------------------------------------------------------- camadas
def src_for(proj, rel): return rel

def place(proj, max_shift=1.5, gap=0.06):
    """Posição real (t0) de cada fala: começa no instante original, mas nunca antes do fim da fala anterior (o inglês costuma ser mais longo)."""
    prev_end = 0.0
    for ph in proj["phrases"]:
        base = ph["lip"]["on"] if ph.get("lip") else ph["s"]       # com rosto visível: a fala começa quando a boca começa
        t0 = max(base, prev_end + gap) if prev_end else base
        t0 = min(t0, base + max_shift)
        ph["t0"] = round(t0, 3)
        prev_end = t0 + (ph["dur"] / max(ph.get("rate", 1), .01) if ph.get("audio") else (ph["e"] - ph["s"]))

def compile_layers(proj):
    place(proj)
    """(Re)gera as camadas automáticas. Camadas criadas pelo usuário (sem auto:true) são preservadas."""
    keep = [l for l in proj["layers"] if not l.get("auto")]
    D = proj["durationSec"]; L = []
    bf = P(proj["id"]) / "media" / "base.mp4"
    base = f"media/base.mp4?v={int(bf.stat().st_mtime)}" if bf.exists() else proj["media"]  # ?v= evita cache velho do navegador
    L.append({"id": "vid", "auto": True, "name": "Vídeo", "type": "video", "start": 0, "duration": D, "src": base, "trimStart": 0,
              "volume": proj["mix"]["original"], "brightness": 1, "contrast": 1.05, "saturate": 1.05, "zoomPunches": []})
    if (P(proj["id"]) / "audio" / "background.wav").exists():
        L.append({"id": "bg", "auto": True, "name": "Fundo (sem a voz)", "type": "audio", "start": 0, "duration": D, "src": "audio/background.wav",
                  "trimStart": 0, "volume": proj["mix"]["background"], "rate": 1})
    if proj.get("cover_old_subs"):
        L.append({"id": "cover", "auto": True, "name": "Vidro (cobre legenda antiga)", "type": "glass", "start": 0, "duration": D, "enter": False,
                  "x": 0.03, "y": 0.66, "w": 0.94, "h": 0.25, "radius": 36, "blur": 60, "tint": "rgba(10,10,14,0.97)", "borderColor": "rgba(255,255,255,0.45)"})
    for ph in proj["phrases"]:
        a = ph.get("audio")
        if a:
            L.append({"id": f"a_{ph['id']}", "auto": True, "phrase": ph["id"], "name": f"{ph['id']} · {ph['speaker']}: {ph['en'][:26]}", "type": "audio",
                      "start": ph["t0"], "duration": round(ph["dur"] / ph.get("rate", 1) + 0.05, 2), "src": a, "trimStart": 0,
                      "volume": proj["mix"]["voice"], "rate": ph.get("rate", 1)})
    for u in keep:
        if u.get("link") == "base" and "src" in u: u["src"] = base  # cartão de vídeo sempre acompanha o vídeo com lip-sync
    cover = [l for l in L if l["id"] == "cover"]  # o vidro fica ACIMA dos recortes (que carregam a legenda antiga queimada)
    proj["layers"] = [l for l in L if l["id"] != "cover"] + keep + cover + [captions_layer(proj)]

def phrase_words(ph, idx):
    toks = (ph.get("en") or "").split()
    if not toks: return []
    D = (ph.get("dur", ph["e"] - ph["s"]) / max(ph.get("rate", 1), .01)) if ph.get("dur") else ph["e"] - ph["s"]
    T0 = ph.get("t0", ph["s"])
    Ltot = sum(len(t) + 2 for t in toks); t = 0.0; out = []
    for tk in toks:
        m = re.match(r"^\*(.+?)\*([.,:;!?]*)$", tk); txt = m.group(1) + m.group(2) if m else tk
        base = re.sub(r"[.,:;!?'’]+$", "", txt).lower()
        dd = D * (len(tk) + 2) / Ltot
        out.append({"text": txt, "start": round(T0 + t, 3), "end": round(T0 + t + dd, 3), "key": bool(m) or base in KEYS or base in {k.lower() for k in ph.get("_keys", [])}, "p": idx})
        t += dd
    return out

def captions_layer(proj):
    words = []
    for i, ph in enumerate(proj["phrases"]): words += phrase_words(ph, i)
    old = next((l for l in proj["layers"] if l.get("id") == "cap"), None)
    base = {k: old[k] for k in ("fontSize", "y", "color", "highlight", "maxChars", "maxWords", "name") if old and k in old}
    return {"id": "cap", "auto": True, "name": "Legendas EN (palavra a palavra)", "type": "captions", "start": 0, "duration": proj["durationSec"], "words": words,
            **{"fontSize": 70, "y": 0.81, "color": "#ffffff", "highlight": "#ffb020", "maxChars": 17, "maxWords": 3}, **base}

def refresh_phrase_layers(proj):
    """Atualiza áudio e legendas das frases sem mexer em camadas do usuário."""
    old = {l["id"]: l for l in proj["layers"]}
    compute_lips(proj["id"], proj)
    compile_layers(proj)
    for l in proj["layers"]:  # preserva ajustes manuais (volume etc.) das camadas automáticas
        o = old.get(l["id"])
        if o and l.get("auto") and l["type"] in ("audio", "video", "glass"):
            for k in ("volume", "brightness", "contrast", "saturate", "zoomPunches", "x", "y", "w", "h", "blur", "tint", "radius", "borderColor"):
                if k in o: l[k] = o[k]

# ---------------------------------------------------------------- sincronia com a leitura labial
LIP_THR = 0.020   # atividade da boca (desvio do MAR em ~0,24 s) a partir da qual a pessoa está falando

def compute_lips(pid, proj=None):
    """Para cada frase com o rosto do falante visível, mede QUANDO a boca começa e termina de se mexer (ph['lip'] = {on, off}).
    A voz em inglês é então colocada nessa janela. Sem rosto visível, a frase usa o tempo da transcrição."""
    proj = proj or store.load(pid); d = P(pid); fc = d / "audio" / "faces.json"
    for ph in proj["phrases"]: ph.pop("lip", None)
    if not fc.exists() or not proj.get("face_groups"): return proj
    frames = [(t, fs) for t, fs in json.loads(fc.read_text())]
    if len(frames) < 10: return proj
    W = (proj.get("native") or [1080])[0]; st = frames[1][0] - frames[0][0]
    chains = faces_mod.tracks(frames, W, st); times = np.array([t for t, _ in frames]); n = len(times)
    k = max(1, int(round(0.12 / st))); act = {}
    for ci, c in enumerate(chains):
        ap = np.full(n, np.nan)
        for i, f in c["pts"].items(): ap[i] = f["mar"]
        a = np.full(n, np.nan)
        for i in range(n):
            win = ap[max(0, i - k): i + k + 1]; win = win[~np.isnan(win)]
            if len(win) >= 3: a[i] = win.std()
        act[ci] = a
    # qual rosto é de qual falante: o rosto cuja boca se mexe mais quando AQUELE falante fala (do que quando ele não fala)
    owner = {}
    for ci, a in act.items():
        best, bs = None, 0.008
        for spk in proj["speakers"]:
            sp_on = np.array([any(p["speaker"] == spk["id"] and p["s"] <= t <= p["e"] for p in proj["phrases"]) for t in times])
            on_v = a[sp_on & ~np.isnan(a)]; off_v = a[~sp_on & ~np.isnan(a)]
            if len(on_v) < 5: continue
            base = float(np.mean(off_v)) if len(off_v) >= 5 else 0.008
            sc = float(np.mean(on_v)) - base
            if sc > bs: best, bs = spk["id"], sc
        if best: owner[ci] = best
    groups = {}
    for ci, sid in owner.items(): groups.setdefault(sid, []).append(int(ci))
    proj["face_groups"] = groups
    need = max(2, int(round(0.2 / st)))
    for ph in proj["phrases"]:
        lo, hi = ph["s"] - 0.4, ph["e"] + 0.5
        idx = np.where((times >= lo) & (times <= hi))[0]
        if len(idx) < 5: continue
        best = None
        for ci in proj["face_groups"].get(ph["speaker"], []):
            a = act.get(ci)
            if a is None: continue
            seg = a[idx]; vis = ~np.isnan(seg)
            if vis.mean() < 0.6: continue
            sc = float(np.nanmean(seg))
            if best is None or sc > best[0]: best = (sc, ci)
        if not best: continue
        seg = act[best[1]][idx]; on = np.nan_to_num(seg, nan=0.0) >= LIP_THR
        runs, i = [], 0
        while i < len(on):
            if on[i]:
                j = i
                while j + 1 < len(on) and (on[j + 1] or (j + 2 < len(on) and on[j + 2])): j += 1   # tolera uma amostra caída
                if j - i + 1 >= need: runs.append((i, j))
                i = j + 1
            else: i += 1
        if not runs: continue
        a0, a1 = times[idx[runs[0][0]]], times[idx[runs[-1][1]]] + st
        L, A = a1 - a0, ph["e"] - ph["s"]
        if 0.6 * A <= L <= 1.5 * A and abs(a0 - ph["s"]) <= 0.7:   # só aceita se for coerente com a transcrição
            ph["lip"] = {"on": round(float(a0), 2), "off": round(float(a1), 2), "chain": int(best[1])}
    return proj

def sync_report(proj):
    """Erro de sincronia: onde a voz em inglês começa/termina em relação à janela em que a boca realmente se mexe."""
    rows = []
    for ph in proj["phrases"]:
        if not ph.get("lip") or not ph.get("audio"): continue
        t0 = ph.get("t0", ph["s"]); end = t0 + ph["dur"] / max(ph.get("rate", 1), 0.01)
        rows.append({"id": ph["id"], "on_err": round(t0 - ph["lip"]["on"], 2), "off_err": round(end - ph["lip"]["off"], 2)})
    if not rows: return {"n": 0}
    return {"n": len(rows), "mean_on": round(float(np.mean([abs(r["on_err"]) for r in rows])), 2), "mean_off": round(float(np.mean([abs(r["off_err"]) for r in rows])), 2), "rows": rows}

# ---------------------------------------------------------------- falantes (voz + boca)
def analyze_speakers(pid, segs, voc16, n_speakers, glossary, progress):
    """Descobre quem fala cada palavra (boca + voz), quebra as frases a cada troca de falante e cria uma voz por pessoa."""
    d = P(pid); proj = store.load(pid); media = d / proj["media"]
    words = [x for s_ in segs for x in s_["words"]]
    av = avdiar.run(media, voc16, words, n_speakers, cache=d / "audio" / "faces.json", progress=progress)
    for w, l in zip(words, av["labels"]): w["spk"] = int(l)
    phrases = build_phrases(segs, protect=re.findall(r"[\wÀ-ú]+", glossary or ""))
    for f in (d / "voices").glob("*"): f.unlink()
    store.update(pid, lambda p: p.__setitem__("voices", []))
    speakers = []
    for k in range(av["n"]):
        sid = f"S{k + 1}"
        ref, secs = speaker_reference_words(pid, sid, voc16, words, k)
        v = make_voice(pid, f"Voz do falante {k + 1}", ref, progress=progress)
        speakers.append({"id": sid, "name": f"Falante {k + 1}", "voice": v["id"], "color": COLORS[k % len(COLORS)]})
    groups = {f"S{k + 1}": g for k, g in enumerate(av.get("chains", []))}
    return speakers, phrases, {"face_groups": groups, "mode": av["mode"]}

# ---------------------------------------------------------------- ingestão
def ingest(pid, language="pt", n_speakers=None, glossary="", progress=lambda m: None, force_asr=False):
    d = P(pid); proj = store.load(pid)
    media = d / proj["media"]
    for f in (d / "voices").glob("*"): f.unlink()  # recomeça as vozes (não acumula perfis antigos)
    def _clr(p): p["voices"] = []; p["speakers"] = []
    store.update(pid, _clr)
    progress("Lendo o vídeo…")
    w, h, fps, total = lipsync.probe(media)
    a16 = d / "audio" / "src16k.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", media, "-vn", "-ac", 1, "-ar", 16000, a16)
    try:
        if (d / "audio" / "vocals.wav").exists() and (d / "audio" / "background.wav").exists():
            voc, bg = d / "audio" / "vocals.wav", d / "audio" / "background.wav"  # já separado antes
        else:
            voc, bg = separate.run(media, d / "audio", progress)
        voc16 = d / "audio" / "vocals16k.wav"
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", voc, "-ac", 1, "-ar", 16000, voc16)
        has_sep = True
    except Exception as e:  # sem Demucs ainda dá para dublar; só não há trilha de fundo limpa
        progress(f"Separação indisponível ({e}); seguindo sem ela."); voc16 = a16; has_sep = False
    tr = d / "audio" / "transcript.json"
    if tr.exists() and not force_asr:
        segs = json.loads(tr.read_text())  # já transcrito (muda só a identificação das vozes etc.)
    else:
        segs = asr.run(voc16, language, glossary or None, progress)
        if not segs and voc16 != a16: segs = asr.run(a16, language, glossary or None, progress)
        tr.write_text(json.dumps(segs, ensure_ascii=False))
    speakers, phrases, info = analyze_speakers(pid, segs, voc16, n_speakers, glossary, progress)
    for p_ in phrases: p_.update({"en": "", "voiced": None, "audio": None, "status": "sem tradução"})
    def fn(p):
        p.update({"width": 1080, "height": 1920, "fps": 30, "durationSec": round(total, 2), "native": [w, h], "speakers": speakers, "phrases": phrases, "face_groups": info.get("face_groups", {}), "diar_mode": info.get("mode", ""),
                  "has_separation": has_sep, "glossary": glossary, "status": "transcrito", "cover_old_subs": p.get("cover_old_subs", False)})
        compile_layers(p)
    store.update(pid, fn)
    return {"phrases": len(phrases), "speakers": len(speakers)}

def rediarize(pid, n_speakers=None, progress=lambda m: None):
    """Refaz a identificação de falantes (voz + boca), as frases e as vozes. Não transcreve de novo; apaga traduções e vozes geradas."""
    d = P(pid); proj = store.load(pid)
    segs = json.loads((d / "audio" / "transcript.json").read_text())
    voc16 = d / "audio" / ("vocals16k.wav" if (d / "audio" / "vocals16k.wav").exists() else "src16k.wav")
    speakers, phrases, info = analyze_speakers(pid, segs, voc16, n_speakers, proj.get("glossary", ""), progress)
    for p_ in phrases: p_.update({"en": "", "voiced": None, "audio": None, "status": "sem tradução"})
    def fn(p):
        p.update({"speakers": speakers, "phrases": phrases, "face_groups": info["face_groups"], "diar_mode": info["mode"]})
        p["layers"] = [l for l in p["layers"] if not l.get("phrase")]
        p["lipsync"]["spans"] = []
        compile_layers(p)
    store.update(pid, fn)
    return {"speakers": len(speakers), "phrases": len(phrases)}

# ---------------------------------------------------------------- tradução
def translate_all(pid, ids=None, progress=lambda m: None):
    if not translate.available(): raise RuntimeError("Tradução automática precisa de ANTHROPIC_API_KEY no servidor. Você pode digitar a tradução à mão.")
    proj = store.load(pid)
    sel = [p for p in proj["phrases"] if not ids or p["id"] in ids]
    progress(f"Traduzindo {len(sel)} frases…")
    res = translate.run(sel, proj.get("glossary", ""))
    def fn(p):
        for ph in p["phrases"]:
            if ph["id"] in res: ph["en"] = res[ph["id"]]; ph["status"] = "sem voz"
        refresh_phrase_layers(p)
    store.update(pid, fn)
    return {"translated": len(res)}

# ---------------------------------------------------------------- voz por frase
def _params_hash(v, say, target=0.0):
    return hashlib.md5(("v5|" + say + json.dumps(v["params"], sort_keys=True) + v["id"] + v["ref"] + str(v.get("builtin")) + f"|{target:.1f}").encode()).hexdigest()[:10]

def say_text(proj, text):
    import unicodedata
    for a, b in (proj.get("pronounce") or {}).items(): text = re.sub(re.escape(a), b, text, flags=re.I)
    # o XTTS trava (pausas longas, silêncio) com letras acentuadas dentro de texto em inglês: Império -> Imperio
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return text.replace("*", "")

def voice_phrase(pid, ph_id, progress=lambda m: None):
    proj = store.load(pid); d = P(pid)
    i = next(k for k, p in enumerate(proj["phrases"]) if p["id"] == ph_id); ph = proj["phrases"][i]
    spk = next(s for s in proj["speakers"] if s["id"] == ph["speaker"]); v = next(x for x in proj["voices"] if x["id"] == spk["voice"])
    if not ph.get("en", "").strip(): raise RuntimeError(f"A frase {ph_id} está sem tradução.")
    say = say_text(proj, ph["en"])
    nxt = proj["phrases"][i + 1]["s"] if i + 1 < len(proj["phrases"]) else ph["e"] + 2.0
    lip = ph.get("lip")
    slot = (lip["off"] - lip["on"]) if lip else max(nxt - ph["s"] - 0.05, ph["e"] - ph["s"])   # com boca visível: cabe na janela dos lábios
    h = _params_hash(v, say, slot if lip else 0.0)
    raw = d / "dub" / f"{ph_id}_{h}_raw.wav"; out = d / "dub" / f"{ph_id}_{h}.wav"
    pr = v["params"]
    if not out.exists():
        progress(f"Gerando a voz da frase {ph_id} ({spk['name']})…")
        base = pr["speed"]; cand = None
        # o XTTS varia muito de uma geração para outra: gera até 3-4 candidatos e fica com o que mais se aproxima da janela-alvo
        speeds = [base, base * 1.2, base * 1.35, base * 1.35] if lip else [base, base * 1.2, base * 1.35]
        for n_try, sp in enumerate(speeds):
            r_ = d / "dub" / f"{ph_id}_{h}_raw{n_try}.wav"; t_ = d / "dub" / f"{ph_id}_{h}_trim{n_try}.wav"
            tts.synth(say, d / v["ref"], r_, speed=min(sp, 1.5), temperature=pr["temperature"], engine=v["engine"], voice_id=v.get("voice_id"), builtin=v.get("builtin"))
            voiceprint.trim_silence(r_, t_); r_.unlink(missing_ok=True); dd0 = tts.duration(t_); f0 = dd0 / slot
            score = abs(float(np.log(f0))) + (0.4 if f0 > 1.4 else 0.0)
            if cand is None or score < cand[0]:
                if cand: cand[1].unlink(missing_ok=True)
                cand = (score, t_, dd0)
            else: t_.unlink(missing_ok=True)
            if 0.88 <= f0 <= 1.06: break
        _, raw, dd0 = cand
        f = dd0 / slot
        # ajuste final SEM mudar o tom (atempo): encaixa na janela da boca (0.85x–1.4x) ou, sem rosto, só acelera (até 1.3x)
        tempo = float(np.clip(f, 0.85, 1.4)) if lip else (float(np.clip(f, 1.0, 1.3)) if f > 1.04 else 1.0)
        semis = pr.get("pitch", 0.0)
        if pr.get("auto_pitch") and v["analysis"].get("f0"): semis += voiceprint.match_semitones(v["analysis"]["f0"], raw)
        voiceprint.pitch_shift(raw, out, semis, pr.get("gain", 1.0), tempo=tempo)
        for k_ in (d / "dub").glob(f"{ph_id}_{h}_trim*.wav"): k_.unlink(missing_ok=True)
    dd = tts.duration(out)
    def fn(p):
        q = p["phrases"][i]
        q.update({"audio": f"dub/{out.name}", "dur": round(dd, 3), "rate": 1.0,
                  "voiced": {"en": ph["en"], "hash": h, "voice": v["id"]}, "status": "ok",
                  "overflow": round(max(0.0, dd - slot), 2)})
        refresh_phrase_layers(p)
    store.update(pid, fn)
    return out.name

def stale_ids(proj):
    out = []
    for ph in proj["phrases"]:
        if not ph.get("en", "").strip(): continue
        spk = next((s for s in proj["speakers"] if s["id"] == ph["speaker"]), None)
        v = next((x for x in proj["voices"] if spk and x["id"] == spk["voice"]), None)
        if not v: continue
        cur = _params_hash(v, say_text(proj, ph["en"]), (ph["lip"]["off"] - ph["lip"]["on"]) if ph.get("lip") else 0.0)
        if not ph.get("audio") or not ph.get("voiced") or ph["voiced"].get("hash") != cur: out.append(ph["id"])
    return out

def voice_all(pid, ids=None, progress=lambda m: None):
    proj = store.load(pid); todo = ids or stale_ids(proj)
    for n, x in enumerate(todo, 1):
        progress(f"Voz {n}/{len(todo)}…"); voice_phrase(pid, x, progress)
    return {"voiced": todo}

def preview_voice(pid, vid, text="This is how this voice sounds. Adjust the tone until it feels right.", progress=lambda m: None):
    proj = store.load(pid); d = P(pid); v = next(x for x in proj["voices"] if x["id"] == vid); pr = v["params"]
    raw = d / "voices" / f"{vid}_prev_raw.wav"; out = d / "voices" / f"{vid}_prev.wav"
    progress("Gerando amostra da voz…")
    tts.synth(text, d / v["ref"], raw, speed=pr["speed"], temperature=pr["temperature"], engine=v["engine"], voice_id=v.get("voice_id"), builtin=v.get("builtin"))
    semis = pr.get("pitch", 0.0)
    if pr.get("auto_pitch") and v["analysis"].get("f0"): semis += voiceprint.match_semitones(v["analysis"]["f0"], raw)
    voiceprint.pitch_shift(raw, out, semis, pr.get("gain", 1.0)); raw.unlink(missing_ok=True)
    return {"file": f"voices/{out.name}", "f0": (voiceprint.f0_stats(out) or {}).get("f0")}

def calibrate_voice(pid, vid, progress=lambda m: None):
    """Gera uma amostra, mede o tom e ajusta os semitons para igualar o tom da voz de referência."""
    proj = store.load(pid); d = P(pid); v = next(x for x in proj["voices"] if x["id"] == vid)
    raw = d / "voices" / f"{vid}_cal.wav"
    progress("Medindo o tom da voz gerada…")
    tts.synth("Calibrating the tone of this voice so it matches the original speaker.", d / v["ref"], raw, speed=v["params"]["speed"], temperature=v["params"]["temperature"], engine=v["engine"], builtin=v.get("builtin"))
    semis = voiceprint.match_semitones(v["analysis"].get("f0"), raw); raw.unlink(missing_ok=True)
    def fn(p):
        x = next(y for y in p["voices"] if y["id"] == vid); x["params"]["pitch"] = round(semis, 2); x["params"]["auto_pitch"] = False
    store.update(pid, fn)
    return {"pitch": round(semis, 2)}

# ---------------------------------------------------------------- lip-sync
def span_audio(pid, proj, span, dst):
    """Áudio dublado do falante do trecho, posicionado como na timeline (para o Wav2Lip)."""
    d = P(pid); s, e = span["s"], span["e"]; ins, fl, k = [], [], 0
    for ph in proj["phrases"]:
        if ph["speaker"] != span["speaker"] or not ph.get("audio"): continue
        t0 = ph.get("t0", ph["s"]); end = t0 + ph["dur"] / ph.get("rate", 1)
        if end < s or t0 > e: continue
        ins += ["-i", str(d / ph["audio"])]; ms = int(max(0, (t0 - s)) * 1000); off = max(0, s - t0)
        fl.append(f"[{k}:a]atempo={ph.get('rate', 1)},atrim=start={off},asetpts=PTS-STARTPTS,adelay={ms}|{ms}[a{k}]"); k += 1
    if not k: raise RuntimeError("O falante deste trecho ainda não tem voz gerada.")
    fl.append("".join(f"[a{j}]" for j in range(k)) + f"amix=inputs={k}:normalize=0,apad=whole_dur={e - s},atrim=0:{e - s}[o]")
    sh("ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fl), "-map", "[o]", dst)

def lipsync_suggest(pid, progress=lambda m: None):
    proj = store.load(pid); d = P(pid)
    fc = d / "audio" / "faces.json"
    frames = [(t, fs) for t, fs in json.loads(fc.read_text())] if fc.exists() else None
    spans = lipsync.suggest_spans(d / proj["media"], proj["phrases"], proj["speakers"], progress, frames=frames, prefer=proj.get("face_groups") or None)
    def fn(p): p["lipsync"]["spans"] = spans
    store.update(pid, fn)
    return {"spans": len(spans)}

def lipsync_run(pid, ids=None, progress=lambda m: None):
    proj = store.load(pid); d = P(pid); video = d / proj["media"]
    todo = [s for s in proj["lipsync"]["spans"] if s.get("enabled") and (not ids or s["id"] in ids)]
    for n, sp in enumerate(todo, 1):
        progress(f"Lip-sync {n}/{len(todo)} ({sp['id']})…")
        wav = d / "lip" / f"{sp['id']}_in.wav"; span_audio(pid, proj, sp, wav)
        f = lipsync.run_span(d, video, sp, wav, progress); wav.unlink(missing_ok=True)
        def fn(p, sid=sp["id"], f=f):
            x = next(y for y in p["lipsync"]["spans"] if y["id"] == sid); x.update({"status": "done", "file": str(f)})
        store.update(pid, fn)
    compose_base(pid)
    return {"done": [s["id"] for s in todo]}

def compose_base(pid):
    proj = store.load(pid); d = P(pid)
    lipsync.compose(d / proj["media"], proj["lipsync"]["spans"], d / "media" / "base.mp4")
    def fn(p): refresh_phrase_layers(p)
    store.update(pid, fn)

# ---------------------------------------------------------------- estilo visual
def detect_cuts(video, thr=0.35):
    r = subprocess.run(["ffmpeg", "-i", str(video), "-vf", f"select='gt(scene,{thr})',showinfo", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r)]

def apply_style(pid, preset="full", title="", tag="", words=None, progress=lambda m: None, end=None, transitions=False):
    """Aplica um visual profissional: fundo animado + letreiro + vídeo em cartão + título + legendas abaixo + transições nos cortes.
    As camadas criadas ficam marcadas (preset) e são substituídas ao aplicar de novo; as suas camadas não são tocadas."""
    proj = store.load(pid); d = P(pid); media = d / proj["media"]; D = proj["durationSec"]
    progress("Achando os cortes de cena…")
    E = min(float(end), D) if end else D          # o visual termina em E; depois aparece o vídeo original em tela cheia (ex.: logo final)
    raw = [c for c in detect_cuts(media, 0.45) if 1.0 < c < E - 1.0]
    cuts = []                                      # só mudanças grandes de cena, bem espaçadas (cortes rápidos ficam como estão)
    for c in raw:
        if not cuts or c - cuts[-1] >= 5.0: cuts.append(c)
    cuts = cuts[:5]
    def mk(**k):
        k.update({"id": "s_" + uuid_hex(), "preset": preset, "auto": False}); return k
    S = []
    if preset == "card":   # opcional (o padrão agora é 'full': só efeitos por cima do vídeo)
        ws = [w.strip() for w in (words or []) if w.strip()] or ([title] if title else [proj.get("name", "KLZ")])
        S += [mk(name="Fundo animado", type="background", start=0, duration=E, style="aurora", c1="#0a0a14", c2="#5b2bd9", c3="#ff6a3d", speed=1, grain=0.2, vignette=0.6),
              mk(name="Letreiro", type="kinetic", start=0, duration=E, mode="marquee", words=ws, fontSize=170, y=0.42, color="#ffffff", accent="#ffb020", outline=True, speed=1, rotate=-8, opacity=0.14),
              mk(name="Vídeo em cartão", type="videoCard", link="base", src=proj["media"], start=0, duration=E, trimStart=0, volume=0, x=0.06, y=0.26, w=0.88, h=0.56,
                 shape="rounded", radius=56, borderColor="rgba(255,255,255,0.4)", borderWidth=3, glow="rgba(124,92,255,0.5)", zoom=1, focusX=0.5, focusY=0.32, enter="rise")]
    if title:
        S.append(mk(name="Título", type="title", start=0.4, duration=min(4.0, D), text=title, tag=tag, y=0.07 if preset == "card" else 0.1, fontSize=108, color="#ffffff", accent="#ffb020", accentLast=True))
    for i, c in enumerate(cuts[:8] if transitions else []):
        S.append(mk(name=f"Transição {i + 1}", type="transition", start=round(max(0, c - 0.45), 2), duration=0.9, kind=["wipe", "bars"][i % 2], color="#7c5cff", color2="#ffb020"))
    if E < D - 0.5:
        S.append(mk(name="Transição final", type="transition", start=round(max(0, E - 0.45), 2), duration=0.9, kind="wipe", color="#7c5cff", color2="#ffb020"))
    def fn(p):
        old = [l for l in p["layers"] if not l.get("preset")]
        for l in old:
            if l.get("id") == "cap":
                l.update({"y": 0.9, "variant": "box", "fontSize": 66} if preset == "card" else {"y": 0.81, "variant": "pop", "fontSize": 70})
        p["cover_old_subs"] = preset != "card"   # tela cheia: o vidro esconde as legendas antigas gravadas no original
        auto = [l for l in old if l.get("auto")]; user = [l for l in old if not l.get("auto")]
        p["layers"] = auto + S + user
        compile_layers(p)
    store.update(pid, fn)
    return {"layers": len(S), "cuts": len(cuts)}

def uuid_hex():
    import uuid; return uuid.uuid4().hex[:6]

# ---------------------------------------------------------------- texto atrás da pessoa
def make_cutout(pid, layer_id, progress=lambda m: None):
    """Gera os PNGs com transparência da(s) pessoa(s) durante a camada 'textBehind' (a pessoa fica por cima do texto)."""
    proj = store.load(pid); d = P(pid)
    l = next((x for x in proj["layers"] if x["id"] == layer_id), None)
    if not l or l.get("type") != "textBehind": raise RuntimeError("Camada de texto atrás da pessoa não encontrada.")
    base = d / "media" / "base.mp4"; video = base if base.exists() else d / proj["media"]
    fc = d / "audio" / "faces.json"
    frames = [(t, fs) for t, fs in json.loads(fc.read_text())] if fc.exists() else None
    out = d / "matte" / layer_id
    if out.exists(): shutil.rmtree(out)
    n = matte.make_cutouts(video, out, l["start"], l["start"] + l["duration"], frames, progress=progress)
    def fn(p):
        x = next(y for y in p["layers"] if y["id"] == layer_id)
        x.update({"cutout": f"matte/{layer_id}", "frames": n, "cutFps": 30, "cutRange": [x["start"], x["duration"]]})
    store.update(pid, fn)
    return {"frames": n}

# ---------------------------------------------------------------- render
def render(pid, scale=0.75, crf=18, base_url="http://127.0.0.1:8000", token="", progress=lambda m: None):
    proj = store.load(pid); d = P(pid)
    layers = json.loads(json.dumps(proj["layers"]))
    for l in layers:
        if "src" in l: l["src"] = f"{base_url}/api/projects/{pid}/files/{l['src'].split('?')[0]}?token={token}"
        if l.get("cutout"): l["cutout"] = f"{base_url}/api/projects/{pid}/files/{l['cutout']}/{{n}}.png?token={token}"
    props = {"fps": proj["fps"], "width": proj["width"], "height": proj["height"], "durationSec": proj["durationSec"], "layers": layers}
    pj = d / "render" / "props.json"; pj.write_text(json.dumps(props, ensure_ascii=False))
    out = d / "render" / f"final_{int(scale * 100)}.mp4"
    progress("Renderizando o vídeo (Remotion)…")
    p = subprocess.Popen(["npx", "remotion", "render", "src/index.ts", "Reel", str(out), f"--props={pj}", f"--scale={scale}", f"--crf={crf}", "--codec=h264"],
                         cwd=STUDIO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail = ""
    for line in p.stdout:
        for chunk in line.replace("\r", "\n").split("\n"):
            if "Rendered" in chunk or "Encoded" in chunk: progress(chunk.strip()[:80])
            tail = (tail + chunk + "\n")[-1500:]
    if p.wait() or not out.exists(): raise RuntimeError("Render falhou: " + tail[-500:])
    return {"file": f"render/{out.name}"}
