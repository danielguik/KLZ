"""Inicia o KLZ Server: python -m server.run  (abra o endereço mostrado no computador ou no celular)."""
import os, socket, sys
import uvicorn
from . import app as appmod
from .config import token

def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("10.255.255.255", 1)); ips.add(s.getsockname()[0]); s.close()
    except Exception: pass
    return sorted(ips)

if __name__ == "__main__":
    port = int(os.environ.get("KLZ_PORT", "8000")); appmod.PORT["n"] = port
    print("\n  KLZ Studio rodando.\n  No computador:  http://localhost:%d/?token=%s" % (port, token()))
    for ip in lan_ips(): print("  No celular (mesmo Wi-Fi):  http://%s:%d/?token=%s" % (ip, port, token()))
    print("  (a senha é o trecho depois de token=)\n")
    uvicorn.run(appmod.app, host=os.environ.get("KLZ_HOST", "0.0.0.0"), port=port, log_level="warning")
