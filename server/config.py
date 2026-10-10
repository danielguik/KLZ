import os, secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("KLZ_DATA", ROOT / "server" / "data"))
DATA.mkdir(parents=True, exist_ok=True)
WHISPER = os.environ.get("KLZ_WHISPER", "large-v3")
CLAUDE_MODEL = os.environ.get("KLZ_MODEL", "claude-sonnet-5-5")
W2L_DIR = Path(os.environ.get("KLZ_W2L", ROOT / "server" / "third_party" / "Wav2Lip"))
STUDIO = ROOT / "studio"

def token() -> str:
    """Senha de acesso (gerada na 1ª execução e guardada em data/token.txt)."""
    p = DATA / "token.txt"
    if not p.exists():
        p.write_text(secrets.token_urlsafe(9))
    return p.read_text().strip()
