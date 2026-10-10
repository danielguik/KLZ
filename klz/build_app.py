"""Monta app/klz-editor.html (arquivo único) com o projeto e a voz da dublagem embutidos.
Uso: python -m klz.build_app"""
import base64, json
from pathlib import Path
R = Path(__file__).resolve().parent.parent
proj = json.load(open(R / "studio/src/projects/door.json"))
keys = sorted({w["text"].strip(".,:;!?'").lower().replace("'s", "") for l in proj["layers"] if l["type"] == "captions" for w in l["words"] if w.get("key")})
wav = {}
for l in proj["layers"]:
    if l["type"] == "audio":
        wav[l["src"]] = base64.b64encode((R / "studio/public" / l["src"]).read_bytes()).decode()
data = {"project": proj, "keys": keys, "wav": wav}
html = (R / "app/template.html").read_text().replace("__DATA__", json.dumps(data, ensure_ascii=False))
(R / "app/klz-editor.html").write_text(html)
print(len(html) // 1024, "KB;", len(wav), "áudios;", len(keys), "palavras-chave")
