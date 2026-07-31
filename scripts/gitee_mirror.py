#!/usr/bin/env python3
"""
gitee_mirror.py — Mirror the local repo to Gitee via pure API (no git binary).

For each file in the local repo, it:
  1. GETs the current file on Gitee to obtain its SHA
  2. PUTs the new content (base64) to update, or create if 404

Usage:
  export GITEE_TOKEN=be94...
  export GITEE_USER=wagziqag
  python3 scripts/gitee_mirror.py [--repo phone-automation-system] [--branch master]
"""
import os, sys, json, base64, time, traceback
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ─── Config ──────────────────────────────────────────────────────────────
GITEE_API = "https://gitee.com/api/v5"
USER      = os.environ.get("GITEE_USER", "wagziqag")
REPO      = os.environ.get("GITEE_REPO", "phone-automation-system")
BRANCH    = os.environ.get("GITEE_BRANCH", "master")
ROOT      = Path(__file__).resolve().parent.parent

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "phone-automation-mirror/1.0",
}

SKIP_DIRS  = {".git", "node_modules", "__pycache__", ".venv", "venv"}
SKIP_FILES = {".d_b64"}
MAX_BYTES  = 5 * 1024 * 1024  # 5MB hard limit for API

# ─── Helpers ──────────────────────────────────────────────────────────────
def auth_params():
    tok = os.environ.get("GITEE_TOKEN", "")
    if not tok:
        sys.exit("ERROR: GITEE_TOKEN not set")
    return f"access_token={tok}"

def api_req(method, url, data=None, retries=3):
    sep = "&" if "?" in url else "?"
    url  = f"{url}{sep}{auth_params()}"
    body = json.dumps(data).encode() if data else None
    for attempt in range(retries):
        try:
            req = Request(url, data=body, method=method, headers=HEADERS)
            with urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode() or "{}")
        except HTTPError as e:
            code = e.code
            msg  = e.read().decode(errors="replace")
            if code == 409 and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1)); continue
            if code == 404:
                return None  # file not found → create
            print(f"  ! HTTP {code}: {msg[:200]}", file=sys.stderr)
            raise

def ensure_repo():
    """Create the Gitee repo if it doesn't exist."""
    r = api_req("GET", f"{GITEE_API}/repos/{USER}/{REPO}")
    if r and "id" in r:
        print(f"✓ Gitee repo exists: {r.get('full_name')}")
        return
    print("→ Creating Gitee repo...")
    api_req("POST", f"{GITEE_API}/user/repos", {
        "name":        REPO,
        "description": "AI phone automation — ADB + Ollama + Gitee queue channel",
        "private":     False,
        "auto_init":   True,
        "has_issues":  True,
    })
    print("✓ Gitee repo created")
    time.sleep(2)

def get_sha(path):
    r = api_req("GET", f"{GITEE_API}/repos/{USER}/{REPO}/contents/{path}?ref={BRANCH}")
    return r.get("sha") if r else None

def upload(local: Path, rel: str):
    content = local.read_bytes()
    if len(content) > MAX_BYTES:
        print(f"  SKIP >5MB: {rel}")
        return False
    b64 = base64.b64encode(content).decode()
    sha = get_sha(rel)
    payload = {
        "message": f"sync: {rel}",
        "content": b64,
        "branch":  BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = api_req("PUT", f"{GITEE_API}/repos/{USER}/{REPO}/contents/{rel}", payload)
    return bool(r)

def collect():
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file(): continue
        rel = p.relative_to(ROOT).as_posix()
        parts = rel.split("/")
        if any(s in SKIP_DIRS for s in parts):  continue
        if parts[-1] in SKIP_FILES:              continue
        out.append((p, rel))
    return out

# ─── Main ─────────────────────────────────────────────────────────────────
def main():
    print(f"Gitee user:  {USER}")
    print(f"Gitee repo:  {REPO}")
    print(f"Branch:      {BRANCH}")
    print(f"Local root:  {ROOT}\n")

    ensure_repo()
    files = collect()
    print(f"Files to sync: {len(files)}\n")

    ok = fail = skip = 0
    for i, (local, rel) in enumerate(sorted(files, key=lambda x: x[1]), 1):
        try:
            changed = upload(local, rel)
            if changed:
                ok += 1
                print(f"  [{i}/{len(files)}] ✓ {rel}  ({local.stat().st_size}B)")
            else:
                skip += 1
        except Exception as e:
            fail += 1
            print(f"  [{i}/{len(files)}] ✗ {rel}  -> {e}")

    print(f"\n{'='*60}")
    print(f"Result: ✓{ok}  ✗{fail}  skip{skip}  total{len(files)}")
    if fail:
        sys.exit(1)
    print(f"\n✓ Gitee mirror complete: https://gitee.com/{USER}/{REPO}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
