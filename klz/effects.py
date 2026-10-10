"""Catálogo de efeitos (estilo painel Effects do After Effects) -> filtros FFmpeg."""

# Cada efeito: label, categoria, parâmetros {nome: (label, min, max, padrão)}, builder(params)->filtro
def _p(**kw):
    return kw

CATALOG = {
    "brightness_contrast": {
        "label": "Brilho e Contraste", "category": "Cor",
        "params": _p(brightness=("Brilho", -1, 1, 0.0), contrast=("Contraste", 0, 3, 1.0), saturation=("Saturação", 0, 3, 1.0)),
        "build": lambda p: f"eq=brightness={p['brightness']}:contrast={p['contrast']}:saturation={p['saturation']}",
    },
    "hue": {
        "label": "Matiz", "category": "Cor",
        "params": _p(degrees=("Graus", -180, 180, 0)),
        "build": lambda p: f"hue=h={p['degrees']}",
    },
    "color_balance": {
        "label": "Balanço de Cor (Teal & Orange)", "category": "Cor",
        "params": _p(shadows_blue=("Sombras azul", -1, 1, 0.2), highlights_red=("Realces vermelho", -1, 1, 0.2)),
        "build": lambda p: f"colorbalance=bs={p['shadows_blue']}:rh={p['highlights_red']}",
    },
    "grayscale": {
        "label": "Preto e Branco", "category": "Cor", "params": {},
        "build": lambda p: "hue=s=0",
    },
    "invert": {
        "label": "Inverter", "category": "Cor", "params": {},
        "build": lambda p: "negate",
    },
    "blur": {
        "label": "Desfoque Gaussiano", "category": "Desfoque e Nitidez",
        "params": _p(sigma=("Intensidade", 0, 50, 5)),
        "build": lambda p: f"gblur=sigma={max(p['sigma'], 0.1)}",
    },
    "sharpen": {
        "label": "Nitidez", "category": "Desfoque e Nitidez",
        "params": _p(amount=("Quantidade", 0, 5, 1.0)),
        "build": lambda p: f"unsharp=5:5:{p['amount']}",
    },
    "vignette": {
        "label": "Vinheta", "category": "Estilizar",
        "params": _p(angle=("Ângulo", 0.1, 1.5, 0.6)),
        "build": lambda p: f"vignette=angle={p['angle']}",
    },
    "film_grain": {
        "label": "Granulado de Filme", "category": "Estilizar",
        "params": _p(strength=("Força", 0, 80, 15)),
        "build": lambda p: f"noise=alls={int(p['strength'])}:allf=t",
    },
    "mirror": {
        "label": "Espelhar", "category": "Transformar", "params": {},
        "build": lambda p: "hflip",
    },
    "rotate": {
        "label": "Rotacionar", "category": "Transformar",
        "params": _p(degrees=("Graus", -180, 180, 0)),
        "build": lambda p: f"rotate={p['degrees']}*PI/180:fillcolor=black",
    },
    "slow_zoom": {
        "label": "Zoom Lento (Ken Burns)", "category": "Transformar",
        "params": _p(speed=("Velocidade", 0.0001, 0.01, 0.0015), max_zoom=("Zoom máx", 1.0, 3.0, 1.3)),
        "build": lambda p: f"zoompan=z='min(zoom+{p['speed']},{p['max_zoom']})':d=1:s={{w}}x{{h}}:fps={{fps}}",
    },
    "fade_in": {
        "label": "Fade In", "category": "Transições",
        "params": _p(duration=("Duração (s)", 0.1, 5, 0.5)),
        "build": lambda p: f"fade=t=in:st=0:d={p['duration']}:alpha=1",
    },
    "fade_out": {
        "label": "Fade Out", "category": "Transições",
        "params": _p(duration=("Duração (s)", 0.1, 5, 0.5)),
        "build": lambda p: f"fade=t=out:st={{end_minus_{p['duration']}}}:d={p['duration']}:alpha=1",
    },
    "chroma_key": {
        "label": "Chroma Key (tela verde)", "category": "Keying",
        "params": _p(similarity=("Similaridade", 0.01, 0.5, 0.15), blend=("Suavização", 0, 0.5, 0.05)),
        "build": lambda p: f"chromakey=0x00FF00:{p['similarity']}:{p['blend']}",
    },
    "speed": {
        "label": "Velocidade", "category": "Tempo",
        "params": _p(factor=("Fator", 0.25, 4, 1.0)),
        "build": lambda p: f"setpts=PTS/{p['factor']}",
    },
}


def defaults(effect_type: str) -> dict:
    return {k: v[3] for k, v in CATALOG[effect_type]["params"].items()}


def catalog_public() -> dict:
    return {
        k: {"label": v["label"], "category": v["category"],
            "params": {n: {"label": s[0], "min": s[1], "max": s[2], "default": s[3]} for n, s in v["params"].items()}}
        for k, v in CATALOG.items()
    }


def build_filter(effect: dict, *, w: int, h: int, fps: int, layer_len: float) -> str:
    spec = CATALOG[effect["type"]]
    params = {**defaults(effect["type"]), **effect.get("params", {})}
    f = spec["build"](params)
    f = f.replace("{w}", str(w)).replace("{h}", str(h)).replace("{fps}", str(fps))
    # fade_out: substitui marcador pelo instante real
    import re
    f = re.sub(r"\{end_minus_([\d.]+)\}", lambda m: f"{max(layer_len - float(m.group(1)), 0):.3f}", f)
    return f
