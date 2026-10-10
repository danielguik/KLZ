"""Tradução PT->EN com Claude (precisa de ANTHROPIC_API_KEY no servidor). Respeita o tempo de fala de cada frase."""
import json, os
from ..config import CLAUDE_MODEL

def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))

def run(phrases, glossary="", style="natural, conversacional, como um falante nativo diria", src="português do Brasil", dst="inglês americano"):
    import anthropic
    items = [{"id": p["id"], "seconds": round(p["e"] - p["s"], 2), "max_chars": int((p["e"] - p["s"]) * 14), "text": p["pt"]} for p in phrases]
    prompt = (f"Você é adaptador profissional de dublagem. Traduza cada trecho de {src} para {dst}, estilo: {style}.\n"
              "Traduza o SENTIDO e a intenção (nunca palavra por palavra); mantenha humor, tom e emoção; nomes próprios e marcas ficam como estão. "
              "Cada tradução deve poder ser falada no tempo 'seconds' (≈14 caracteres por segundo): respeite 'max_chars' reformulando e encurtando. "
              "Frases vizinhas formam um discurso contínuo: mantenha a coesão.\n"
              + (f"Glossário/nomes corretos: {glossary}\n" if glossary else "")
              + 'Responda SOMENTE um array JSON: [{"id":"...","en":"..."}]\n\n' + json.dumps(items, ensure_ascii=False))
    msg = anthropic.Anthropic().messages.create(model=CLAUDE_MODEL, max_tokens=8000, messages=[{"role": "user", "content": prompt}])
    txt = msg.content[0].text
    data = json.loads(txt[txt.index("["): txt.rindex("]") + 1])
    return {d["id"]: d["en"] for d in data}
