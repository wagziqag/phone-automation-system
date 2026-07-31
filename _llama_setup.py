
import subprocess, json, base64, urllib.request, os
import os

T = os.environ.get("GITEE_TOKEN", "")
result = {"stage": "check"}

def sh(cmd, timeout=20):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 检查是否已有 llama.cpp
rc, out, _ = sh("ls ~/llama.cpp/CMakeLists.txt 2>&1")
if rc == 0:
    result["stage"] = "exists"
    result["exists"] = True
    rc, out, _ = sh("ls ~/llama.cpp/build/bin/ 2>&1 | head -10")
    result["build_bin"] = out[:300]
else:
    result["exists"] = False
    # 克隆 OpenMOSS 的 llama.cpp fork
    result["stage"] = "cloning"
    rc, out, err = sh("cd ~ && git clone https://github.com/OpenMOSS/llama.cpp.git --depth 1 2>&1", 60)
    result["clone"] = {"rc": rc, "out": (out+err)[:500]}
    
    if rc == 0:
        result["stage"] = "cloned"
        # 检查 CMakeLists
        rc, out, _ = sh("ls ~/llama.cpp/CMakeLists.txt 2>&1")
        result["cmake_exists"] = (rc == 0)

    # 检查磁盘空间
    rc, out, _ = sh("df -h ~ 2>&1 | tail -2")
    result["disk"] = out[:200]

b=base64.b64encode(json.dumps(result,ensure_ascii=False).encode()).decode()
r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/llama_setup.json?access_token={T}")
try:
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"llama_setup"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/llama_setup.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15): pass
