"""Motion graphics: legendas animadas palavra a palavra (ASS), cartões de vidro e transições (xfade)."""
import subprocess

# ---------- Legendas animadas ----------
def _t(s):  # ASS time h:mm:ss.cc
    h, r = divmod(max(s, 0), 3600); m, r = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{r:05.2f}"


def build_ass(words, w, h, keywords=(), font="DejaVu Sans", base=0.052, key_color="&H0040C8FF", y_frac=0.74, group=4):
    """words: [{'start','end','text'}]. Mostra grupos de `group` palavras; a palavra falada ganha 'pop' e
    as palavras-chave ficam maiores, coloridas e permanecem destacadas até o fim do grupo."""
    fs, kfs = int(h * base), int(h * base * 1.35)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n"
            f"[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,"
            f"Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: W,{font},{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,{max(2, fs // 14)},2,5,40,40,0,1\n\n"
            f"[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    kws = {k.lower() for k in keywords}
    out = []
    for g in range(0, len(words), group):
        chunk = words[g:g + group]
        g_end = chunk[-1]["end"]
        for i, cur in enumerate(chunk):
            start = cur["start"]
            end = chunk[i + 1]["start"] if i + 1 < len(chunk) else g_end
            parts = []
            for j, wd in enumerate(chunk):
                txt = wd["text"].strip().replace("{", "(")
                is_key = txt.lower().strip(".,!?;:") in kws
                if j > i:
                    parts.append(f"{{\\alpha&HFF&}}{txt}")           # ainda não falada: invisível (mantém layout)
                elif j == i:                                          # palavra atual: pop de escala
                    tags = f"\\fscx60\\fscy60\\t(0,120,\\fscx118\\fscy118)\\t(120,220,\\fscx100\\fscy100)"
                    if is_key:
                        tags += f"\\c{key_color}\\fs{kfs}\\t(0,150,\\fscx135\\fscy135)"
                    parts.append(f"{{{tags}}}{txt}{{\\r}}")
                else:                                                 # já falada: fica; chave continua destacada
                    parts.append(f"{{\\c{key_color}\\fs{kfs}}}{txt}{{\\r}}" if is_key else txt)
            line = " ".join(parts)
            out.append(f"Dialogue: 0,{_t(start)},{_t(end)},W,,0,0,0,,{{\\an5\\pos({w // 2},{int(h * y_frac)})}}{line}")
    return head + "\n".join(out) + "\n"


# ---------- Vidro (glassmorphism) ----------
def glass_filter(x, y, w, h, start, end, blur=18, tint="white@0.14", border="white@0.55", bw=2, inp="0:v", out="vg", tag="g"):
    """Retângulo 'vidro fosco': recorta a região, desfoca, escurece/clareia levemente e põe borda translúcida."""
    en = f"enable='between(t,{start:.2f},{end:.2f})'"
    return (f"[{inp}]split[{tag}a][{tag}b];"
            f"[{tag}b]crop={w}:{h}:{x}:{y},gblur=sigma={blur},eq=brightness=0.04:saturation=1.25[{tag}c];"
            f"[{tag}a][{tag}c]overlay={x}:{y}:{en}[{tag}d];"
            f"[{tag}d]drawbox=x={x}:y={y}:w={w}:h={h}:color={tint}:t=fill:{en},"
            f"drawbox=x={x}:y={y}:w={w}:h={h}:color={border}:t={bw}:{en}[{out}]")


# ---------- Transições ----------
TRANSITIONS = ["fade", "wipeleft", "wiperight", "slideleft", "slideright", "circleopen", "circleclose",
               "dissolve", "pixelize", "radial", "zoomin", "smoothleft", "smoothright", "fadeblack"]


def xfade_chain(n_clips, durs, kind="fade", td=0.5):
    """Filtro xfade encadeando n clipes [0:v][1:v]... Retorna (filter, out_label)."""
    parts, last, acc = [], "0:v", durs[0]
    for i in range(1, n_clips):
        t = kind[i % len(kind)] if isinstance(kind, list) else kind
        parts.append(f"[{last}][{i}:v]xfade=transition={t}:duration={td}:offset={acc - td:.3f}[x{i}]")
        last, acc = f"x{i}", acc + durs[i] - td
    return ";".join(parts), last


def burn(src, ass_path, dst, glass=None, extra_vf=None, crf=18):
    """Aplica vidro (lista de dicts) + legendas ASS ao vídeo. Mantém áudio original."""
    fc, last = [], "0:v"
    for i, g in enumerate(glass or []):
        fc.append(glass_filter(**g, inp=last, out=f"vg{i}", tag=f"g{i}"))
        last = f"vg{i}"
    esc = ass_path.replace("\\", "/").replace(":", "\\:")
    fc.append(f"[{last}]ass='{esc}'{(',' + extra_vf) if extra_vf else ''}[vout]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "0:a?",
           "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "copy", dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1200:])
