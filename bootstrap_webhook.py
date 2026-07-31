"""
bootstrap_webhook.py — Webhook 模式启动器

功能：
  1. 建立 Serveo/Cloudflared 隧道，暴露 8098 端口
  2. 启动 webhook_server.py
  3. 上传隧道 URL 到 Gitee（tunnel_url.txt）
  4. 守护进程保活

运行方式：
  python bootstrap_webhook.py

依赖：
  pip install flask
  ssh (Serveo) 或 cloudflared
"""

import subprocess
import threading
import time
import os
import signal
import sys
import json
import base64
import urllib.request
from pathlib import Path

# ─── 配置 ─────────────────────────────────────────────
GITEE_TOKEN = os.environ.get("GITEE_TOKEN", "be94810b75731a166c301f752d5348e8")
GITEE_USER = "wagziqag"
GITEE_REPO = "phone-automation-system"
GITEE_API = f"https://gitee.com/api/v5/repos/{GITEE_USER}/{GITEE_REPO}/contents"
TUNNEL_FILE = "tunnel_url.txt"
WEBHOOK_PORT = 8098
BASE_DIR = Path.home() / "phone-automation-system"
TUNNEL_URL_PATH = Path.home() / ".tunnel_url.txt"

# 全局状态
tunnel_url = None
webhook_process = None
tunnel_process = None
keeper_running = True


def run(cmd, timeout=30, shell=True):
    """执行命令"""
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def gitee_get(path):
    """从 Gitee 读取文件"""
    url = f"{GITEE_API}/{path}?access_token={GITEE_TOKEN}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as f:
            data = json.loads(f.read())
        if isinstance(data, list):
            return None, None
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    except Exception as e:
        print(f"[GITEE] GET {path} failed: {e}")
        return None, None


def gitee_put(path, content_str, sha, message="update"):
    """上传文件到 Gitee"""
    b64 = base64.b64encode(content_str.encode()).decode()
    payload = {
        "access_token": GITEE_TOKEN,
        "content": b64,
        "message": message,
    }
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(
        f"{GITEE_API}/{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json;charset=UTF-8"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as f:
            return True
    except Exception as e:
        print(f"[GITEE] PUT {path} failed: {e}")
        return False


def upload_tunnel_url(url):
    """上传隧道 URL 到 Gitee"""
    content, sha = gitee_get(TUNNEL_FILE)
    gitee_put(TUNNEL_FILE, url, sha, f"tunnel: {url}")
    TUNNEL_URL_PATH.write_text(url)
    print(f"[TUNNEL] URL uploaded: {url}")


# ─── 隧道管理 ────────────────────────────────────────
def start_serveo_tunnel():
    """通过 Serveo SSH 建立隧道"""
    global tunnel_url
    print("[TUNNEL] Starting Serveo tunnel...")

    # kill existing tunnels on port 8098
    os.system("pkill -f 'ssh.*8098:localhost:8098' 2>/dev/null || true")
    time.sleep(1)

    cmd = (
        f"ssh -o StrictHostKeyChecking=no "
        f"-o ServerAliveInterval=30 "
        f"-o LogLevel=ERROR "
        f"-R 0:localhost:{WEBHOOK_PORT} "
        f"serveo.net 2>&1"
    )

    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )

    # 解析 Serveo 输出的 URL（格式：Forwarding HTTP traffic from https://xxx.serveo.net）
    deadline = time.time() + 60
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        if "Forwarding" in line or "serveo.net" in line:
            # 提取 URL
            import re
            m = re.search(r'https?://[\w\-]+\.serveo\.\w+', line)
            if m:
                tunnel_url = m.group(0)
                print(f"[TUNNEL] Got URL: {tunnel_url}")
                upload_tunnel_url(tunnel_url)
                return proc
        if time.time() > deadline:
            print("[TUNNEL] Timed out waiting for Serveo URL")
            proc.kill()
            return None

    return proc


def start_cloudflared_tunnel():
    """通过 Cloudflared 建立隧道（fallback）"""
    global tunnel_url
    print("[TUNNEL] Trying Cloudflared...")

    os.system("pkill -f 'cloudflared.*8098' 2>/dev/null || true")
    time.sleep(1)

    cmd = f"cloudflared tunnel --url http://localhost:{WEBHOOK_PORT} 2>&1"

    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )

    deadline = time.time() + 60
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        import re
        m = re.search(r'https?://[\w\-]+\.trycloudflare\.com', line)
        if m:
            tunnel_url = m.group(0)
            print(f"[TUNNEL] Got URL: {tunnel_url}")
            upload_tunnel_url(tunnel_url)
            return proc
        if time.time() > deadline:
            print("[TUNNEL] Timed out waiting for Cloudflared URL")
            proc.kill()
            return None

    return proc


def start_tunnel():
    """启动隧道，Serveo 优先，Cloudflared fallback"""
    p = start_serveo_tunnel()
    if p:
        return p
    print("[TUNNEL] Serveo failed, falling back to Cloudflared...")
    return start_cloudflared_tunnel()


# ─── Webhook 服务管理 ─────────────────────────────────
def start_webhook():
    """启动 webhook_server.py"""
    global webhook_process
    script = BASE_DIR / "webhook_server.py"

    if not script.exists():
        print(f"[WEBHOOK] Script not found: {script}")
        print("[WEBHOOK] Pull from Gitee first: git pull")
        return None

    cmd = f"python {script} --port {WEBHOOK_PORT} --host 0.0.0.0"

    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )

    # 等待服务就绪
    deadline = time.time() + 10
    while time.time() < deadline:
        rc, out, err = run(f"curl -s http://localhost:{WEBHOOK_PORT}/health", timeout=3)
        if rc == 0:
            print("[WEBHOOK] Server is ready")
            return proc
        time.sleep(1)

    print("[WEBHOOK] Server started but health check failed")
    return proc


def output_reader(proc, tag):
    """读取子进程输出"""
    try:
        for line in proc.stdout:
            if line.strip():
                print(f"[{tag}] {line.strip()}")
    except Exception:
        pass


# ─── 守护逻辑 ────────────────────────────────────────
def keeper():
    """守护进程：监控并重启服务"""
    global tunnel_process, webhook_process, keeper_running

    while keeper_running:
        # 检查 Webhook 服务
        if webhook_process and webhook_process.poll() is not None:
            print("[KEEPER] Webhook died, restarting...")
            webhook_process = start_webhook()

        # 检查隧道
        if tunnel_process and tunnel_process.poll() is not None:
            print("[KEEPER] Tunnel died, restarting...")
            tunnel_process = start_tunnel()

        # 心跳上报
        try:
            content, sha = gitee_get("heartbeat.json")
            gitee_put("heartbeat.json",
                       json.dumps({"last_seen": time.time(), "mode": "webhook"}),
                       sha, "webhook heartbeat")
        except Exception:
            pass

        time.sleep(30)


def cleanup(sig, frame):
    """清理信号处理"""
    global keeper_running
    print("\n[CLEANUP] Shutting down...")
    keeper_running = False

    for p in [webhook_process, tunnel_process]:
        if p:
            try:
                p.kill()
            except Exception:
                pass

    sys.exit(0)


# ─── 主入口 ──────────────────────────────────────────
if __name__ == "__main__":
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=" * 60)
    print("  Webhook Mode Bootstrap")
    print(f"  Port: {WEBHOOK_PORT}")
    print("=" * 60)

    # 1. 启动 Webhook 服务
    webhook_process = start_webhook()
    if not webhook_process:
        print("[FATAL] Failed to start webhook server")
        sys.exit(1)

    # 2. 启动隧道
    tunnel_process = start_tunnel()
    if not tunnel_process:
        print("[FATAL] Failed to start tunnel")
        cleanup(None, None)

    # 3. 启动输出阅读线程
    for proc, tag in [(webhook_process, "WEBHOOK"), (tunnel_process, "TUNNEL")]:
        if proc:
            t = threading.Thread(target=output_reader, args=(proc, tag), daemon=True)
            t.start()

    # 4. 启动守护线程
    t_keeper = threading.Thread(target=keeper, daemon=True)
    t_keeper.start()

    # 5. 保持主线程
    print("\n[READY] Webhook mode active. Press Ctrl+C to stop.")
    try:
        while keeper_running:
            time.sleep(10)
    except KeyboardInterrupt:
        cleanup(None, None)
