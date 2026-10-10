"""Dublagem PT -> EN: transcrição (Whisper) -> tradução natural (Claude) -> voz (ElevenLabs c/ clonagem ou OpenAI TTS)
-> ajuste de tempo (atempo) -> camadas de áudio na timeline.

Chaves (variáveis de ambiente):
  ANTHROPIC_API_KEY   tradução e agente
  ELEVENLABS_API_KEY  voz ultrarrealista + clonagem da voz original (recomendado)
  OPENAI_API_KEY      transcrição (se faster-whisper não estiver instalado) e TTS de fallback
"""
import json, os, subprocess, tempfile
from pathlib import Path
import httpx
from . import project as P

MODEL = os.environ.get("KLZ_MODEL", "claude-sonnet-5-5")


def extract_audio(src, dst, start=0.0, end=None):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-i", src]
    if end:
        cmd += ["-t", str(end - start)]
    subprocess.run(cmd + ["-vn", "-ac", "1", "-ar", "16000", dst], check=True)


def transcribe(audio_path, language="pt"):
    """Retorna [{start,end,text}]."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(os.environ.get("KLZ_WHISPER", "large-v3"), compute_type="auto")
        segs, _ = model.transcribe(audio_path, language=language, vad_filter=True)
        return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs]
    except ImportError:
        pass
    key = os.environ["OPENAI_API_KEY"]
    with open(audio_path, "rb") as f:
        r = httpx.post("https://api.openai.com/v1/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
                       files={"file": f}, data={"model": "whisper-1", "language": language,
                                                "response_format": "verbose_json"}, timeout=600)
    r.raise_for_status()
    return [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in r.json()["segments"]]


def translate(segments, source="Brazilian Portuguese", target="American English", style="natural, conversational"):
    """Tradução por significado e intenção (não literal), respeitando o tempo de fala de cada trecho."""
    import anthropic
    items = [{"i": i, "seconds": round(s["end"] - s["start"], 2), "text": s["text"]} for i, s in enumerate(segments)]
    prompt = (
        f"You are a professional dubbing adapter. Translate these {source} subtitle segments into {target}.\n"
        f"Style: {style}. Use idioms and phrasing a native speaker would actually say; keep humor, tone, emotion and "
        "register. Never translate word-for-word. Each line must be speakable in roughly its 'seconds' at ~15 characters "
        "per second — shorten or rephrase if needed, keep the meaning. Keep proper nouns. Context flows across segments.\n"
        'Return ONLY a JSON array: [{"i":0,"text":"..."}]\n\n' + json.dumps(items, ensure_ascii=False))
    msg = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=8000, messages=[{"role": "user", "content": prompt}])
    txt = msg.content[0].text
    data = json.loads(txt[txt.index("["): txt.rindex("]") + 1])
    by_i = {d["i"]: d["text"] for d in data}
    return [{**s, "en": by_i[i]} for i, s in enumerate(segments)]


def clone_voice(sample_wav, name="klz-clone"):
    key = os.environ["ELEVENLABS_API_KEY"]
    with open(sample_wav, "rb") as f:
        r = httpx.post("https://api.elevenlabs.io/v1/voices/add", headers={"xi-api-key": key},
                       files={"files": f}, data={"name": name}, timeout=300)
    r.raise_for_status()
    return r.json()["voice_id"]


def tts(text, out_mp3, voice_id=None):
    if os.environ.get("ELEVENLABS_API_KEY"):
        key = os.environ["ELEVENLABS_API_KEY"]
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id or os.environ.get('ELEVENLABS_VOICE', '21m00Tcm4TlvDq8ikWAM')}",
                       headers={"xi-api-key": key}, json={"text": text, "model_id": "eleven_multilingual_v2",
                       "voice_settings": {"stability": 0.4, "similarity_boost": 0.85, "style": 0.3}}, timeout=300)
    else:
        r = httpx.post("https://api.openai.com/v1/audio/speech",
                       headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                       json={"model": "gpt-4o-mini-tts", "voice": "ash", "input": text}, timeout=300)
    r.raise_for_status()
    Path(out_mp3).write_bytes(r.content)


def duration(path):
    return P.probe(path)["duration"]


def fit_to_slot(src, dst, slot, max_speedup=1.35):
    """Acelera levemente (atempo) se a fala em inglês passar do tempo do original."""
    d = duration(src)
    f = min(max(d / slot, 1.0), max_speedup) if slot > 0 else 1.0
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter:a", f"atempo={f:.3f}", dst], check=True)
    return duration(dst)


def dub_layer(proj, layer_id, project_name, clone=True, mute_original=True, progress=print):
    """Dubla uma camada de vídeo/áudio. Adiciona camadas 'EN dub' e silencia a original."""
    layer = P.find(proj, layer_id)
    src = proj["assets"][layer["asset"]]["path"]
    work = Path(P.PROJECTS) / project_name / "dub" / layer_id
    work.mkdir(parents=True, exist_ok=True)
    wav = str(work / "src.wav")
    extract_audio(src, wav, layer["in"], layer["out"])
    progress("Transcrevendo (PT)…")
    segs = transcribe(wav)
    progress(f"Traduzindo {len(segs)} trechos para inglês natural…")
    segs = translate(segs)
    voice = clone_voice(wav) if clone and os.environ.get("ELEVENLABS_API_KEY") else None
    created = []
    for i, s in enumerate(segs):
        progress(f"Gerando voz {i + 1}/{len(segs)}…")
        raw, fit = str(work / f"{i}.mp3"), str(work / f"{i}_fit.mp3")
        tts(s["en"], raw, voice)
        fit_to_slot(raw, fit, s["end"] - s["start"])
        aid = P.add_asset(proj, fit, f"EN {i}")
        c = P.add_clip(proj, aid, start=layer["start"] + s["start"])
        c["name"] = f"EN: {s['en'][:30]}"
        created.append(c["id"])
    if mute_original:
        layer["volume"] = 0.0
    (work / "segments.json").write_text(json.dumps(segs, ensure_ascii=False, indent=2))
    return {"segments": segs, "layers": created}
