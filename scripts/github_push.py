#!/usr/bin/env python3
"""
github_push.py — Push phone-automation-system to GitHub via REST API.

No git binary required. Uses the GitHub Contents API + Git Data API to:
  1. Create or update files in wagziqag/phone-automation-system
  2. Create a commit via the Git Data API
  3. Optionally mirror to Gitee

Usage:
  export GITHUB_TOKEN=ghp_xxx
  python3 scripts/github_push.py [--branch main] [--message "msg"] [--gitee]

Environment:
  GITHUB_TOKEN  GitHub personal access token (required)
  GITHUB_USER   GitHub username (default: wagziqag)
  GITEE_TOKEN   Gitee access token (optional, for mirror)
  GITEE_USER    Gitee username   (optional, for mirror)
"""
import os, sys, json, base64, hashlib, time, argparse, traceback
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ─── Config ────────────────────────────────────────────────────────────────
REPO     = os.environ.get("GITHUB_USER", "wagziqag") + "/phone-automation-system"
BRANCH   = "main"
API      = "https://api.github.com"
HEADERS  = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "phone-automation-push/1.0",
}
ROOT     = Path(__file__).resolve().parent.parent  # repo root

# Skip rules
SKIP_DIRS  = {".git", "node_modules", "__pycache__", ".venv", "venv"}
SKIP_FILES = {".d_b64"}  # encrypted blob, handle separately
MAX_BYTES  = 80 * 1024    # GitHub contents API limit per file

# ─── Helpers ───────────────────────────────────────────────────────────────
def auth_headers():
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not tok:
        sys.exit("ERROR: GITHUB_TOKEN not set. export GITHUB_TOKEN=ghp_xxx")
    return {**HEADERS, "Authorization": f"Bearer {tok}"}

def api_req(method, url, data=None, retries=3):
    for attempt in range(retries):
        try:
            body = json.dumps(data).encode() if data else None
            req = Request(url, data=body, method=method, headers=auth_headers())
            with urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode() or "{}")
        except HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code == 409 and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"  ! HTTP {e.code}: {msg[:200]}", file=sys.stderr)
            raise

def get_sha(path):
    """Return the current SHA of a file at path, or None if it doesn't exist."""
    try:
        r = api_req("GET", f"{API}/repos/{REPO}/contents/{path}?ref={BRANCH}")
        return r.get("sha")
    except HTTPError as e:
        if e.code == 404:
            return None
        raise

def upload_file(local_path: Path, repo_path: str):
    """Upload one file. Returns True if changed."""
    content = local_path.read_bytes()
    b64 = base64.b64encode(content).decode()
    sha = get_sha(repo_path)
    payload = {
        "message": f"chore: sync {repo_path}",
        "content": b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    try:
        api_req("PUT", f"{API}/repos/{REPO}/contents/{repo_path}", payload)
        return True
    except HTTPError as e:
        if e.code == 422 and b"should be smaller" in e.read().decode(errors="replace").lower():
            # Too large for contents API → fall back to Git Data API
            return upload_large(local_path, repo_path, sha)
        raise

def upload_large(local_path: Path, repo_path: str, sha: str | None):
    """Use Git Data API for files > 80KB."""
    content = local_path.read_bytes()
    # 1. Create blob
    blob = api_req("POST", f"{API}/repos/{REPO}/git/blobs", {
        "content": base64.b64encode(content).decode(),
        "encoding": "base64",
    })
    blob_sha = blob["sha"]
    # 2. Get current tree
    branch = api_req("GET", f"{API}/repos/{REPO}/branches/{BRANCH}")
    base_tree = branch["commit"]["commit"]["tree"]["sha"]
    # 3. Create new tree
    tree = api_req("POST", f"{API}/repos/{REPO}/git/trees", {
        "base_tree": base_tree,
        "tree": [{"path": repo_path, "mode": "100644", "type": "blob", "sha": blob_sha}],
    })
    # 4. Create commit
    commit = api_req("POST", f"{API}/repos/{REPO}/git/commits", {
        "message": f"chore: sync large file {repo_path}",
        "tree": tree["sha"],
        "parents": [branch["commit"]["sha"]],
    })
    # 5. Update ref
    api_req("PATCH", f"{API}/repos/{REPO}/git/refs/heads/{BRANCH}", {
        "sha": commit["sha"],
    })
    return True

def collect_files():
    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        parts = rel.split("/")
        if any(part in SKIP_DIRS for part in parts):
            continue
        if parts[-1] in SKIP_FILES:
            continue
        if p.stat().st_size > 5 * 1024 * 1024:
            print(f"  SKIP (>{5}MB): {rel}")
            continue
        files.append((p, rel))
    return files

# ─── Gitee mirror (optional) ──────────────────────────────────────────────
def mirror_to_gitee():
    g_token = os.environ.get("GITEE_TOKEN", "")
    g_user  = os.environ.get("GITEE_USER", "wagziqag")
    if not g_token:
        print("  (GITEE_TOKEN not set, skipping Gitee mirror)")
        return
    print("  → Mirroring to Gitee...")
    # Use Gitee Import API to pull from GitHub
    url = f"https://gitee.com/api/v5/repos/{g_user}/phone-automation-system"
    # Simple approach: push via HTTPS using token
    import subprocess
    remote = f"https://{g_user}:{g_token}@gitee.com/{g_user}/phone-automation-system.git"
    try:
        subprocess.run(["git", "remote", "add", "gitee", remote], cwd=ROOT, check=False)
        subprocess.run(["git", "push", "--force", "gitee", BRANCH], cwd=ROOT, check=True, timeout=120)
        print("  ✓ Gitee mirror done")
    except Exception as e:
        print(f"  ! Gitee mirror failed: {e}")

# ─── Main ──────────────────────────────────────────────────────────────────
def main():
    global BRANCH
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--message", default="chore: full sync via github_push.py")
    ap.add_argument("--gitee", action="store_true", help="Also mirror to Gitee")
    args = ap.parse_args()
    BRANCH = args.branch

    print(f"Repository: {REPO}")
    print(f"Branch:     {BRANCH}")
    print(f"Root:       {ROOT}")
    print()

    # Verify auth
    try:
        u = api_req("GET", f"{API}/user")
        print(f"✓ Authenticated as: {u.get('login')} (id={u.get('id')})")
    except Exception as e:
        sys.exit(f"✗ Auth failed: {e}")

    # Check repo exists
    try:
        r = api_req("GET", f"{API}/repos/{REPO}")
        print(f"✓ Repo found: {r.get('full_name')} (default_branch={r.get('default_branch')})")
        # Align branch name
        default = r.get("default_branch", BRANCH)
        if default != BRANCH:
            print(f"  (using default branch '{default}' instead of '{BRANCH}')")
            BRANCH = default
    except HTTPError as e:
        if e.code == 404:
            sys.exit(f"✗ Repo {REPO} not found. Create it first at https://github.com/new")
        raise

    # Collect & upload
    files = collect_files()
    print(f"\nFiles to sync: {len(files)}\n")

    ok = fail = skip = 0
    for i, (local, rel) in enumerate(sorted(files, key=lambda x: x[1]), 1):
        try:
            changed = upload_file(local, rel)
            if changed:
                ok += 1
                print(f"  [{i}/{len(files)}] ✓ {rel}  ({local.stat().st_size}B)")
            else:
                skip += 1
        except Exception as e:
            fail += 1
            print(f"  [{i}/{len(files)}] ✗ {rel}  -> {e}")

    print(f"\n{'='*60}")
    print(f"Upload complete: ✓{ok}  ✗{fail}  skip{fail} (unchanged)")
    if fail:
        sys.exit(1)

    # Gitee mirror
    if args.gitee:
        mirror_to_gitee()

    print("\n✓ All done. GitHub repo is up to date.")
    print(f"  → https://github.com/{REPO}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
