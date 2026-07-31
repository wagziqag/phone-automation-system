#!/data/data/com.termux/files/usr/bin/bash
# Bootstrap: one command to start everything
import os
echo "=== Marvis Bootstrap ==="
cd ~

# Kill old poller
pkill -f poller_v9 2>/dev/null
sleep 1

# Ensure stunnel
if ! which stunnel >/dev/null 2>&1; then
    echo "Installing stunnel+openssl..."
    pkg install -y stunnel openssl 2>&1 | tail -3
fi

# Setup stunnel cert if missing
if [ ! -f ~/.stunnel.pem ]; then
    echo "Generating cert..."
    openssl req -x509 -newkey rsa:2048         -keyout ~/.ollama.key -out ~/.ollama.crt         -days 365 -nodes -subj "/CN=localhost"
    cat ~/.ollama.key ~/.ollama.crt > ~/.stunnel.pem
fi

# Start stunnel if not running
if ! pgrep -f "stunnel.*stunnel.conf" >/dev/null 2>&1; then
    cat > ~/.stunnel.conf <<'EOF'
pid =
[ollama-tls]
accept = 11435
connect = 127.0.0.1:11434
cert = /data/data/com.termux/files/home/.stunnel.pem
EOF
    echo "Starting stunnel..."
    nohup stunnel ~/.stunnel.conf > ~/stunnel.log 2>&1 &
    sleep 2
    # Verify
    curl -sk https://127.0.0.1:11435/v1/models 2>&1 | head -5
fi

echo "=== Stunnel ready ==="

# Pull poller from Gitee
echo "Pulling poller..."
curl -sk "https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/poller_v9.py?access_token=" + os.environ.get("GITEE_TOKEN", "") + "" | python3 -c "import sys,json,base64; d=json.load(sys.stdin); print(base64.b64decode(d['content']).decode())" > ~/poller_v9.py

echo "Starting poller..."
nohup python3 ~/poller_v9.py > ~/poller.log 2>&1 &
sleep 2
echo "Poller PID: $(pgrep -f poller_v9)"
echo "=== Bootstrap done ==="
