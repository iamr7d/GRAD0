"""One-off: give the live stream a permanent address on your own domain, e.g. https://live.example.com

    python -m channel.setup_domain live.example.com

The domain must use Cloudflare for its DNS (free plan is fine; a new domain can be bought
in the Cloudflare dashboard under Domain Registration). This:
  1. signs cloudflared in to your Cloudflare account (a browser window opens: pick the domain),
  2. creates a tunnel called prime-earth-news,
  3. points the address at it,
  4. saves the address in tunnel.json, so python -m channel.live --public (and go_live.bat) use it.
Run it again with another address to move the stream. Your Cloudflare credentials stay in
your user folder (.cloudflared); nothing secret is written to the repo.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .config import ROOT

TUNNEL_FILE = ROOT / "tunnel.json"
NAME = "prime-earth-news"


def cloudflared():
    exe = shutil.which("cloudflared")
    if not exe:
        sys.exit("Install cloudflared once with:  winget install --id Cloudflare.cloudflared\n"
                 "then open a new PowerShell window and run this again.")
    return exe


def run(*args, check=True):
    print("  >", "cloudflared", " ".join(args[1:]))
    r = subprocess.run(args, text=True, capture_output=True)
    if check and r.returncode:
        sys.exit((r.stderr or r.stdout).strip())
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host", help="the address to stream on, e.g. live.example.com or example.com")
    a = ap.parse_args()
    host = re.sub(r"^https?://", "", a.host.strip()).strip("/").lower()
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host):
        sys.exit(f"'{a.host}' doesn't look like a web address (e.g. live.example.com).")
    exe = cloudflared()

    if not (Path.home() / ".cloudflared" / "cert.pem").exists():
        print("1. Signing in to Cloudflare: a browser window opens, log in and click the domain you'll use.")
        subprocess.run([exe, "tunnel", "login"], check=True)
    else:
        print("1. Already signed in to Cloudflare.")

    print("2. Tunnel")
    tunnels = json.loads(run(exe, "tunnel", "list", "--output", "json").stdout or "null") or []
    if any(t.get("name") == NAME for t in tunnels):
        print(f"  using the existing tunnel '{NAME}'")
    else:
        run(exe, "tunnel", "create", NAME)

    print(f"3. Pointing {host} at the tunnel")
    r = run(exe, "tunnel", "route", "dns", "--overwrite-dns", NAME, host, check=False)
    if r.returncode:
        sys.exit((r.stderr or r.stdout).strip() + f"\n\nCheck that {host} is a domain in the Cloudflare account you signed in "
                 "with. If it's in another account, delete %USERPROFILE%\\.cloudflared\\cert.pem and run this again.")

    TUNNEL_FILE.write_text(json.dumps({"name": NAME, "host": host}, indent=2))
    print(f"4. Saved. From now on go_live.bat (or python -m channel.live --public) streams to:\n\n   https://{host}/\n")


if __name__ == "__main__":
    main()
