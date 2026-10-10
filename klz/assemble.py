"""Monta o vídeo final dublado: áudio XTTS por frase + legendas animadas + vidro. Roda no Python do sistema."""
import json, subprocess, sys
from pathlib import Path
from . import motion as M

KW = "hopedale massachusetts império fourteen 14 snow sunshine beautiful rafael fast shapes led presence sensor doormax alucomax minimalist recessed handle unlocking available exclusive celsius".split()


def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True).stdout)


def run(w, total=64.6, out="dublado_v2.mp4", base=None):
    w = Path(w); ph = json.load(open(w/"phrases.json")); info = json.load(open(w/"xtts_info.json"))
    ins, fl, words = [], [], []
    for k, (p, x) in enumerate(zip(ph, info)):
        src = w/"xtts"/x["file"]; d = dur(str(src)); f = max(1.0, d / x["slot"]) if d > x["slot"] else 1.0
        ins += ["-i", str(src)]; ms = int(p["s"]*1000)
        fl.append(f"[{k}:a]atempo={min(f,1.15):.3f},adelay={ms}|{ms}[a{k}]")
        d2 = d / min(f, 1.5); toks = p["en"].split(); L = sum(len(t)+2 for t in toks); t = p["s"]
        for tk in toks:
            dd = d2*(len(tk)+2)/L; words.append({"start":t,"end":t+dd,"text":tk,"p":k}); t += dd
    fl.append("".join(f"[a{k}]" for k in range(len(ph))) + f"amix=inputs={len(ph)}:normalize=0,loudnorm=I=-16:TP=-1.5,apad=whole_dur={total}[o]")
    subprocess.run(["ffmpeg","-y","-loglevel","error",*ins,"-filter_complex",";".join(fl),"-map","[o]","-t",str(total),str(w/"dub_en2.wav")],check=True)
    json.dump(words, open(w/"words_en2.json","w"), indent=1)
    (w/"en2.ass").write_text(M.build_ass(words, 478, 850, keywords=KW, base=0.038, y_frac=0.825, group=3))
    M.burn(base or str(w/"media/original.mp4"), str(w/"en2.ass"), str(w/"v2_mudo.mp4"),
           glass=[dict(x=14,y=625,w=450,h=150,start=0,end=70,blur=30,tint="black@0.35",border="white@0.5")], crf=20)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(w/"v2_mudo.mp4"),"-i",str(w/"dub_en2.wav"),"-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k","-t",str(total),str(w/out)],check=True)
    return str(w/out)

if __name__ == "__main__":
    print(run(sys.argv[1], out=sys.argv[2] if len(sys.argv) > 2 else "dublado_v2.mp4", base=sys.argv[3] if len(sys.argv) > 3 else None))
