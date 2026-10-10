"""Compila o projeto num comando FFmpeg e renderiza (preview ou final)."""
import subprocess
from . import effects
from .project import total_duration, find  # noqa


def _esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def build_cmd(proj, out_path, preview=False):
    W, H, FPS = proj["width"], proj["height"], proj["fps"]
    if preview:
        W, H = W // 2 // 2 * 2, H // 2 // 2 * 2
    dur = max(total_duration(proj), 0.1)
    inputs, fc, v_last, a_labels = [], [], "base", []
    fc.append(f"color=c=black:s={W}x{H}:r={FPS}:d={dur:.3f}[base]")
    idx = 0
    for n, l in enumerate(proj["layers"]):
        length = l["out"] - l["in"]
        s, e = l["start"], l["start"] + length
        asset = proj["assets"].get(l.get("asset", ""))
        if l["type"] == "video":
            inputs += ["-i", asset["path"]]
            chain = [f"trim=start={l['in']:.3f}:end={l['out']:.3f}", "setpts=PTS-STARTPTS",
                     f"scale={int(W * l.get('scale', 1))}:-2", f"fps={FPS}", "format=yuva420p"]
            for ef in l["effects"]:
                chain.append(effects.build_filter(ef, w=W, h=H, fps=FPS, layer_len=length))
            if l.get("opacity", 1) < 1:
                chain.append(f"colorchannelmixer=aa={l['opacity']}")
            chain.append(f"setpts=PTS+{s:.3f}/TB")
            fc.append(f"[{idx}:v]{','.join(chain)}[v{n}]")
            fc.append(f"[{v_last}][v{n}]overlay=x=(W-w)/2+{l.get('x', 0)}:y=(H-h)/2+{l.get('y', 0)}:"
                      f"enable='between(t,{s:.3f},{e:.3f})':eof_action=pass[o{n}]")
            v_last = f"o{n}"
            if asset["has_audio"]:
                a_labels.append(_audio(fc, idx, n, l, s))
            idx += 1
        elif l["type"] == "audio":
            inputs += ["-i", asset["path"]]
            a_labels.append(_audio(fc, idx, n, l, s))
            idx += 1
        elif l["type"] == "text":
            x = "(w-text_w)/2" if l["x"] == "center" else l["x"]
            y = {"bottom": "h-text_h-60", "top": "60", "center": "(h-text_h)/2"}.get(l["y"], l["y"])
            fc.append(f"[{v_last}]drawtext=text='{_esc(l['text'])}':fontsize={int(l['size'] * W / proj['width'])}:"
                      f"fontcolor={l['color']}:borderw=3:bordercolor=black:x={x}:y={y}:"
                      f"enable='between(t,{s:.3f},{e:.3f})'[o{n}]")
            v_last = f"o{n}"
    maps = ["-map", f"[{v_last}]"]
    if a_labels:
        fc.append("".join(f"[{a}]" for a in a_labels) + f"amix=inputs={len(a_labels)}:normalize=0,atrim=0:{dur:.3f}[aout]")
        maps += ["-map", "[aout]"]
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), *maps,
           "-c:v", "libx264", "-preset", "ultrafast" if preview else "medium", "-crf", "30" if preview else "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", f"{dur:.3f}", out_path]
    return cmd


def _audio(fc, idx, n, l, start):
    d = int(start * 1000)
    fc.append(f"[{idx}:a]atrim=start={l['in']:.3f}:end={l['out']:.3f},asetpts=PTS-STARTPTS,"
              f"volume={l.get('volume', 1.0)},adelay={d}|{d}[a{n}]")
    return f"a{n}"


def render(proj, out_path, preview=False):
    if not proj["layers"]:
        raise ValueError("projeto vazio")
    r = subprocess.run(build_cmd(proj, out_path, preview), capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    return out_path
