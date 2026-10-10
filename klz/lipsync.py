"""Correção labial grátis (Wav2Lip, CPU) só nos trechos com rosto. Requer o repo Wav2Lip + pesos em W2L (ver LICOES.md).
   Uso (venv py3.11): python klz/lipsync.py <pasta_projeto> <audio_dublado.wav>"""
import subprocess, sys
from pathlib import Path

W2L = "/tmp/t/w2l"; PY = "/tmp/t/venv/bin/python"
SPANS = [(0.0, 15.4), (42.8, 52.0)]   # trechos com rosto (detecção Haar a cada 1s)


def sh(*a): subprocess.run([str(x) for x in a], check=True)


def run(proj, audio, total=64.62):
    proj = Path(proj); src = proj / "media/original.mp4"; parts = []
    cuts = [0.0] + [t for s in SPANS for t in s] + [total]
    for k in range(len(cuts) - 1):
        a, b = cuts[k], cuts[k + 1]; seg = proj / f"seg{k}.mp4"
        if b - a < 0.05:
            continue  # trecho vazio (-t 0 viraria o vídeo inteiro)
        sh("ffmpeg", "-y", "-loglevel", "error", "-ss", a, "-t", b - a, "-i", src, "-an", "-c:v", "libx264", "-crf", 14, "-r", 30, seg)
        if (a, b) in SPANS:
            wav = proj / f"seg{k}.wav"; out = proj / f"seg{k}_lip.mp4"
            sh("ffmpeg", "-y", "-loglevel", "error", "-ss", a, "-t", b - a, "-i", audio, wav)
            sh(PY, f"{W2L}/inference.py", "--checkpoint_path", f"{W2L}/checkpoints/wav2lip_gan.pth", "--face", seg, "--audio", wav,
               "--outfile", out, "--nosmooth", "--face_det_batch_size", 4, "--wav2lip_batch_size", 32, "--pads", 0, 8, 0, 0)
            # inference.py devolve vídeo+áudio; descartamos áudio e normalizamos
            seg2 = proj / f"seg{k}_lipv.mp4"; sh("ffmpeg", "-y", "-loglevel", "error", "-i", out, "-an", "-c:v", "libx264", "-crf", 14, "-r", 30, seg2); seg = seg2
        parts.append(seg)
    lst = proj / "parts.txt"; lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    base = proj / "base_lip.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", base)
    return str(base)


if __name__ == "__main__":
    print(run(sys.argv[1], sys.argv[2]))
