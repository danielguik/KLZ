"""Agente de edição: Claude com ferramentas que modificam o mesmo projeto JSON que a UI edita."""
import json, os
import anthropic
from . import project as P, effects, dubbing

MODEL = os.environ.get("KLZ_MODEL", "claude-sonnet-5-5")

SYSTEM = f"""Você é um editor de vídeo profissional dentro do app KLZ. Edita a timeline do usuário usando as ferramentas.
Responda em português, de forma curta. Tempos em segundos. Antes de editar, chame get_project para ver o estado atual.
Efeitos disponíveis: {json.dumps({k: v['label'] for k, v in effects.CATALOG.items()}, ensure_ascii=False)}.
Para dublar PT->EN use dub_to_english (demora; avise o usuário). Nunca invente ids; use os de get_project."""

TOOLS = [
    {"name": "get_project", "description": "Retorna o projeto atual (assets, camadas, efeitos).", "input_schema": {"type": "object", "properties": {}}},
    {"name": "add_clip", "description": "Adiciona um asset à timeline.", "input_schema": {"type": "object", "properties": {
        "asset_id": {"type": "string"}, "start": {"type": "number"}, "in": {"type": "number"}, "out": {"type": "number"}}, "required": ["asset_id"]}},
    {"name": "add_text", "description": "Adiciona legenda/título.", "input_schema": {"type": "object", "properties": {
        "text": {"type": "string"}, "start": {"type": "number"}, "duration": {"type": "number"}, "size": {"type": "integer"},
        "color": {"type": "string"}, "y": {"type": "string", "description": "top|center|bottom"}}, "required": ["text", "start", "duration"]}},
    {"name": "split_layer", "description": "Corta uma camada no tempo `at` da timeline.", "input_schema": {"type": "object", "properties": {
        "layer_id": {"type": "string"}, "at": {"type": "number"}}, "required": ["layer_id", "at"]}},
    {"name": "trim_layer", "description": "Ajusta in/out (trecho da fonte) e/ou start (posição) de uma camada.", "input_schema": {"type": "object", "properties": {
        "layer_id": {"type": "string"}, "start": {"type": "number"}, "in": {"type": "number"}, "out": {"type": "number"}}, "required": ["layer_id"]}},
    {"name": "delete_layer", "description": "Remove uma camada.", "input_schema": {"type": "object", "properties": {"layer_id": {"type": "string"}}, "required": ["layer_id"]}},
    {"name": "set_layer", "description": "Define propriedades: opacity, volume, x, y, scale, text, size, color.", "input_schema": {"type": "object", "properties": {
        "layer_id": {"type": "string"}, "props": {"type": "object"}}, "required": ["layer_id", "props"]}},
    {"name": "add_effect", "description": "Aplica efeito a uma camada de vídeo.", "input_schema": {"type": "object", "properties": {
        "layer_id": {"type": "string"}, "effect": {"type": "string", "enum": list(effects.CATALOG)}, "params": {"type": "object"}}, "required": ["layer_id", "effect"]}},
    {"name": "remove_effect", "description": "Remove efeito pelo índice.", "input_schema": {"type": "object", "properties": {
        "layer_id": {"type": "string"}, "index": {"type": "integer"}}, "required": ["layer_id", "index"]}},
    {"name": "dub_to_english", "description": "Transcreve, traduz PT->EN de forma natural e gera dublagem em inglês para a camada.", "input_schema": {
        "type": "object", "properties": {"layer_id": {"type": "string"}}, "required": ["layer_id"]}},
]


def run_tool(name, a, proj, pname):
    if name == "get_project":
        return proj
    if name == "add_clip":
        return P.add_clip(proj, a["asset_id"], a.get("start", 0.0), a.get("in", 0.0), a.get("out"))
    if name == "add_text":
        return P.add_text(proj, a["text"], a["start"], a["duration"], a.get("size", 64), a.get("color", "white"), y=a.get("y", "bottom"))
    if name == "split_layer":
        return P.split(proj, a["layer_id"], a["at"])
    if name == "trim_layer":
        l = P.find(proj, a["layer_id"])
        for k in ("start", "in", "out"):
            if k in a:
                l[k] = a[k]
        return l
    if name == "delete_layer":
        proj["layers"] = [l for l in proj["layers"] if l["id"] != a["layer_id"]]
        return "ok"
    if name == "set_layer":
        P.find(proj, a["layer_id"]).update(a["props"])
        return "ok"
    if name == "add_effect":
        P.find(proj, a["layer_id"])["effects"].append({"type": a["effect"], "params": a.get("params", {})})
        return "ok"
    if name == "remove_effect":
        P.find(proj, a["layer_id"])["effects"].pop(a["index"])
        return "ok"
    if name == "dub_to_english":
        r = dubbing.dub_layer(proj, a["layer_id"], pname)
        return {"segments": len(r["segments"]), "sample": [s["en"] for s in r["segments"][:3]]}
    raise ValueError(f"ferramenta desconhecida {name}")


def chat(pname, history, user_text):
    """Loop de ferramentas. Salva o projeto ao final. Retorna (texto, history)."""
    client = anthropic.Anthropic()
    proj = P.load(pname)
    history = history + [{"role": "user", "content": user_text}]
    for _ in range(20):
        resp = client.messages.create(model=MODEL, max_tokens=4000, system=SYSTEM, tools=TOOLS, messages=history)
        history.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                try:
                    out, err = run_tool(b.name, b.input, proj, pname), False
                except Exception as e:  # devolve o erro ao modelo para ele corrigir
                    out, err = str(e), True
                results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": err,
                                "content": json.dumps(out, ensure_ascii=False)})
        history.append({"role": "user", "content": results})
    P.save(pname, proj)
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, history
