"""Fluxo completo: ingestão (separar voz/fundo, transcrever, identificar falantes), tradução, vozes por falante,
refazer só frases editadas, lip-sync por trecho, montagem das camadas e render final."""
import hashlib, json, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np, soundfile as sf
from . import store
from .config import STUDIO, W2L_DIR
from .engines import asr, diar, separate, tts, voiceprint, translate, lipsync

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
            out.append({"s": round(cur[0]["start"], 2), "e": round(cur[-1]["end"], 2), "pt": " ".join(w["text"] for w in cur)})
        cur = []
    def sent_start(j):  # palavra j abre uma nova sentença (maiúscula sem ponto antes; nomes do glossário e palavras funcionais não contam)
        if j <= 0 or j >= len(words): return False
        t, prev = words[j]["text"], words[j - 1]["text"]
        return (t[:1].isupper() and not prev[:1].isupper() and not re.search(r"[.?!,;:]$", prev) and prev.lower().strip(",.") not in PT_FUNC and t.lower().strip(",.") not in prot)
    for i, w in enumerate(words):
        if cur:
            d0 = cur[-1]["end"] - cur[0]["start"]
            if w["start"] - cur[-1]["end"] > 0.6 or (sent_start(i) and len(cur) >= 2 and d0 >= 1.0): flush()
        cur.append(w)
        d = w["end"] - cur[0]["start"]
        near = next((words[j]["start"] for j in range(i + 1, min(i + 6, len(words))) if sent_start(j)), None)
        tail_short = near is not None and near - w["end"] < 1.3  # restaria só uma sobra curta antes da próxima sentença
        if (re.search(r"[.?!]$", w["text"]) and d >= 1.8) or (re.search(r"[,;:]$", w["text"]) and d >= 2.6 and not tail_short) or d >= max_dur + 1.5: flush()
    flush()
    # sobras muito curtas (<0.8 s) voltam para a frase anterior
    merged = []
    for p in out:
        if merged and (p["e"] - p["s"] < 0.8) and p["s"] - merged[-1]["e"] < 0.8:
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
def make_voice(pid, name, src_audio, speaker=None, progress=lambda m: None):
    """Cria um perfil de voz a partir de um áudio: limpa, corta ~25s de fala e analisa o tom."""
    d = P(pid); proj = store.load(pid)
    vid = f"V{len(proj['voices']) + 1}"
    ref = d / "voices" / f"{vid}.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", src_audio, "-ac", 1, "-ar", 22050, "-af",
       "silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_threshold=-45dB:stop_duration=0.4,highpass=f=70", "-t", 25, ref)
    an = voiceprint.analyze(ref)
    voice = {"id": vid, "name": name, "ref": f"voices/{vid}.wav", "engine": "xtts", "analysis": an,
             "params": {"speed": 1.0, "temperature": 0.6, "pitch": 0.0, "gain": 1.0, "auto_pitch": False}}
    def fn(p): p["voices"].append(voice)
    store.update(pid, fn)
    return voice

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

def compile_layers(proj):
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
                  "x": 0.03, "y": 0.725, "w": 0.94, "h": 0.17, "radius": 36, "blur": 34, "tint": "rgba(10,10,14,0.5)", "borderColor": "rgba(255,255,255,0.45)"})
    for ph in proj["phrases"]:
        a = ph.get("audio")
        if a:
            L.append({"id": f"a_{ph['id']}", "auto": True, "phrase": ph["id"], "name": f"{ph['id']} · {ph['speaker']}: {ph['en'][:26]}", "type": "audio",
                      "start": ph["s"], "duration": round(ph["dur"] / ph.get("rate", 1) + 0.05, 2), "src": a, "trimStart": 0,
                      "volume": proj["mix"]["voice"], "rate": ph.get("rate", 1)})
    L.append(captions_layer(proj))
    proj["layers"] = L + keep

def phrase_words(ph, idx):
    toks = (ph.get("en") or "").split()
    if not toks: return []
    D = (ph.get("dur", ph["e"] - ph["s"]) / max(ph.get("rate", 1), .01)) if ph.get("dur") else ph["e"] - ph["s"]
    Ltot = sum(len(t) + 2 for t in toks); t = 0.0; out = []
    for tk in toks:
        m = re.match(r"^\*(.+?)\*([.,:;!?]*)$", tk); txt = m.group(1) + m.group(2) if m else tk
        base = re.sub(r"[.,:;!?'’]+$", "", txt).lower()
        dd = D * (len(tk) + 2) / Ltot
        out.append({"text": txt, "start": round(ph["s"] + t, 3), "end": round(ph["s"] + t + dd, 3), "key": bool(m) or base in KEYS or base in {k.lower() for k in ph.get("_keys", [])}, "p": idx})
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
    compile_layers(proj)
    for l in proj["layers"]:  # preserva ajustes manuais (volume etc.) das camadas automáticas
        o = old.get(l["id"])
        if o and l.get("auto") and l["type"] in ("audio", "video", "glass"):
            for k in ("volume", "brightness", "contrast", "saturate", "zoomPunches", "x", "y", "w", "h", "blur", "tint", "radius", "borderColor"):
                if k in o: l[k] = o[k]

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
    words = [x for s in segs for x in s["words"]]
    phrases = build_phrases(segs, protect=re.findall(r"[\wÀ-ú]+", glossary or ""))
    labels, chunks, n = diar.run(voc16, words, n_speakers, progress=progress)
    assign_speakers(phrases, labels, chunks)
    speakers, voices = [], []
    for k in range(n):
        sid = f"S{k + 1}"
        ref = speaker_reference(pid, sid, voc16, labels, chunks, k)
        v = make_voice(pid, f"Voz do falante {k + 1}", ref, progress=progress)
        speakers.append({"id": sid, "name": f"Falante {k + 1}", "voice": v["id"], "color": COLORS[k % len(COLORS)]})
    for p_ in phrases: p_.update({"en": "", "voiced": None, "audio": None, "status": "sem tradução"})
    def fn(p):
        p.update({"width": 1080, "height": 1920, "fps": 30, "durationSec": round(total, 2), "native": [w, h], "speakers": speakers, "phrases": phrases,
                  "has_separation": has_sep, "glossary": glossary, "status": "transcrito", "cover_old_subs": p.get("cover_old_subs", False)})
        compile_layers(p)
    store.update(pid, fn)
    return {"phrases": len(phrases), "speakers": len(speakers)}

def rediarize(pid, n_speakers=None, progress=lambda m: None):
    """Refaz só a identificação de falantes e as vozes de referência (rápido: não transcreve de novo). Zera as vozes geradas."""
    d = P(pid); proj = store.load(pid)
    segs = json.loads((d / "audio" / "transcript.json").read_text()); words = [x for s in segs for x in s["words"]]
    voc16 = d / "audio" / ("vocals16k.wav" if (d / "audio" / "vocals16k.wav").exists() else "src16k.wav")
    labels, chunks, n = diar.run(voc16, words, n_speakers, progress=progress)
    for f in (d / "voices").glob("*"): f.unlink()
    phrases = proj["phrases"]; assign_speakers(phrases, labels, chunks)
    speakers = []
    def fn(p): p["voices"] = []
    store.update(pid, fn)
    for k in range(n):
        sid = f"S{k + 1}"; ref = speaker_reference(pid, sid, voc16, labels, chunks, k)
        v = make_voice(pid, f"Voz do falante {k + 1}", ref, progress=progress)
        speakers.append({"id": sid, "name": f"Falante {k + 1}", "voice": v["id"], "color": COLORS[k % len(COLORS)]})
    def fn2(p):
        p["speakers"] = speakers; p["phrases"] = phrases
        for ph in p["phrases"]: ph.update({"audio": None, "voiced": None})
        p["layers"] = [l for l in p["layers"] if not l.get("phrase")]
        refresh_phrase_layers(p)
    store.update(pid, fn2)
    return {"speakers": n}

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
def _params_hash(v, say):
    return hashlib.md5(("v2|" + say + json.dumps(v["params"], sort_keys=True) + v["id"] + v["ref"]).encode()).hexdigest()[:10]

def say_text(proj, text):
    for a, b in (proj.get("pronounce") or {}).items(): text = re.sub(re.escape(a), b, text, flags=re.I)
    return text.replace("*", "")

def voice_phrase(pid, ph_id, progress=lambda m: None):
    proj = store.load(pid); d = P(pid)
    i = next(k for k, p in enumerate(proj["phrases"]) if p["id"] == ph_id); ph = proj["phrases"][i]
    spk = next(s for s in proj["speakers"] if s["id"] == ph["speaker"]); v = next(x for x in proj["voices"] if x["id"] == spk["voice"])
    if not ph.get("en", "").strip(): raise RuntimeError(f"A frase {ph_id} está sem tradução.")
    say = say_text(proj, ph["en"]); h = _params_hash(v, say)
    nxt = proj["phrases"][i + 1]["s"] if i + 1 < len(proj["phrases"]) else ph["e"] + 2.0
    slot = max(nxt - ph["s"] - 0.05, ph["e"] - ph["s"])
    raw = d / "dub" / f"{ph_id}_{h}_raw.wav"; out = d / "dub" / f"{ph_id}_{h}.wav"
    pr = v["params"]
    if not out.exists():
        progress(f"Gerando a voz da frase {ph_id} ({spk['name']})…")
        speed = pr["speed"]; trimmed = d / "dub" / f"{ph_id}_{h}_trim.wav"
        for _ in range(3):  # se passar do tempo da fala original, acelera um pouco (até 1.35x)
            tts.synth(say, d / v["ref"], raw, speed=speed, temperature=pr["temperature"], engine=v["engine"], voice_id=v.get("voice_id"))
            voiceprint.trim_silence(raw, trimmed); dd = tts.duration(trimmed)
            if dd <= slot * 1.03 or speed >= 1.35: break
            speed = min(speed * dd / slot, 1.35)
        raw.unlink(missing_ok=True); raw = trimmed
        semis = pr.get("pitch", 0.0)
        if pr.get("auto_pitch") and v["analysis"].get("f0"): semis += voiceprint.match_semitones(v["analysis"]["f0"], raw)
        voiceprint.pitch_shift(raw, out, semis, pr.get("gain", 1.0)); raw.unlink(missing_ok=True)
    dd = tts.duration(out)
    def fn(p):
        q = p["phrases"][i]
        q.update({"audio": f"dub/{out.name}", "dur": round(dd, 3), "rate": round(max(1.0, min(dd / slot, 1.15)), 3) if dd > slot else 1.0,
                  "voiced": {"en": ph["en"], "hash": h, "voice": v["id"]}, "status": "ok",
                  "overflow": round(max(0.0, dd / (round(max(1.0, min(dd / slot, 1.15)), 3) if dd > slot else 1.0) - slot), 2)})
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
        cur = _params_hash(v, say_text(proj, ph["en"]))
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
    tts.synth(text, d / v["ref"], raw, speed=pr["speed"], temperature=pr["temperature"], engine=v["engine"], voice_id=v.get("voice_id"))
    semis = pr.get("pitch", 0.0)
    if pr.get("auto_pitch") and v["analysis"].get("f0"): semis += voiceprint.match_semitones(v["analysis"]["f0"], raw)
    voiceprint.pitch_shift(raw, out, semis, pr.get("gain", 1.0)); raw.unlink(missing_ok=True)
    return {"file": f"voices/{out.name}", "f0": (voiceprint.f0_stats(out) or {}).get("f0")}

def calibrate_voice(pid, vid, progress=lambda m: None):
    """Gera uma amostra, mede o tom e ajusta os semitons para igualar o tom da voz de referência."""
    proj = store.load(pid); d = P(pid); v = next(x for x in proj["voices"] if x["id"] == vid)
    raw = d / "voices" / f"{vid}_cal.wav"
    progress("Medindo o tom da voz gerada…")
    tts.synth("Calibrating the tone of this voice so it matches the original speaker.", d / v["ref"], raw, speed=v["params"]["speed"], temperature=v["params"]["temperature"], engine=v["engine"])
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
        end = ph["s"] + ph["dur"] / ph.get("rate", 1)
        if end < s or ph["s"] > e: continue
        ins += ["-i", str(d / ph["audio"])]; ms = int(max(0, (ph["s"] - s)) * 1000); off = max(0, s - ph["s"])
        fl.append(f"[{k}:a]atempo={ph.get('rate', 1)},atrim=start={off},asetpts=PTS-STARTPTS,adelay={ms}|{ms}[a{k}]"); k += 1
    if not k: raise RuntimeError("O falante deste trecho ainda não tem voz gerada.")
    fl.append("".join(f"[a{j}]" for j in range(k)) + f"amix=inputs={k}:normalize=0,apad=whole_dur={e - s},atrim=0:{e - s}[o]")
    sh("ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fl), "-map", "[o]", dst)

def lipsync_suggest(pid, progress=lambda m: None):
    proj = store.load(pid); d = P(pid)
    spans = lipsync.suggest_spans(d / proj["media"], proj["phrases"], proj["speakers"], progress)
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

# ---------------------------------------------------------------- render
def render(pid, scale=0.75, crf=18, base_url="http://127.0.0.1:8000", token="", progress=lambda m: None):
    proj = store.load(pid); d = P(pid)
    layers = json.loads(json.dumps(proj["layers"]))
    for l in layers:
        if "src" in l: l["src"] = f"{base_url}/api/projects/{pid}/files/{l['src'].split('?')[0]}?token={token}"
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
