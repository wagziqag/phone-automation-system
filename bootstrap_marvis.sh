#!/data/data/com.termux/files/usr/bin/bash
set -e; cd ~/phone-automation-system
echo "[BOOT] $(date +%H:%M:%S)"
git pull 2>/dev/null || true
pkill -f poller_v8.py 2>/dev/null; pkill -f tool_executor.py 2>/dev/null; pkill -f v4_server.py 2>/dev/null
sleep 2
echo "  tool_executor:5000"; setsid python3 tool_executor.py --port 5000 > /tmp/te.log 2>&1 < /dev/null & disown
sleep 2
echo "  v4_server:8099"; setsid python3 v4_server.py > /tmp/v4.log 2>&1 < /dev/null & disown
sleep 3
curl -s -m 5 http://127.0.0.1:19998/status 2>/dev/null || echo "  ZT not running"
echo "=== HEALTH ==="
curl -s -m 3 http://127.0.0.1:5000/health 2>/dev/null || echo "  TE DOWN"
curl -s -m 3 http://127.0.0.1:8099/health 2>/dev/null || echo "  V4 DOWN"
curl -s -m 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 80 || echo "  OL DOWN"
echo "  poller"; setsid python3 poller_v8.py > /tmp/pl.log 2>&1 < /dev/null & disown
sleep 5
echo "[BOOT] DONE $(date +%H:%M:%S)"
# 可选：启动自主 Agent
# python3 phone_agent.py loop --steps 10 &
