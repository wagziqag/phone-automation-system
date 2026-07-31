
import subprocess, json, base64, urllib.request, os
import os

T = os.environ.get("GITEE_TOKEN", "")
result = {"stage": "start"}

def sh(cmd, timeout=30):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()[-500:], r.stderr.strip()[-300:]
    except Exception as e:
        return -1, "", str(e)[:200]

# Step 1: 切换 remote 到 OpenMOSS fork + git reset
result["stage"] = "switch_remote"
cmds = [
    "cd ~/llama.cpp && git remote set-url origin https://github.com/OpenMOSS/llama.cpp.git",
    "cd ~/llama.cpp && git stash 2>/dev/null; git reset --hard HEAD",
    "cd ~/llama.cpp && git fetch origin main --depth 1 2>&1 | tail -5",
    "cd ~/llama.cpp && git checkout -B main origin/main 2>&1 | tail -3",
]
for c in cmds:
    rc, out, err = sh(c, 30)
    result[c[:60]] = {"rc": rc, "out": (out+err)[:200]}

# 验证 remote
rc, out, _ = sh("cd ~/llama.cpp && git remote -v")
result["remote_after"] = out[:200]

# Step 2: 完整清理重建
result["stage"] = "clean"
rc, out, _ = sh("rm -rf ~/llama.cpp/build && mkdir -p ~/llama.cpp/build", 5)

# Step 3: cmake（修正参数）
result["stage"] = "cmake"
rc, out, err = sh(
    "cd ~/llama.cpp/build && cmake .. -DGGML_NATIVE=OFF -DLLAMA_CURL=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON 2>&1",
    90
)
result["cmake"] = {"rc": rc, "tail": (out+err)[-500:]}

# Step 4: make
if rc == 0:
    result["stage"] = "make"
    rc, out, err = sh("cd ~/llama.cpp/build && make -j4 llama-cli llama-server 2>&1", 180)
    result["make_main"] = {"rc": rc, "tail": (out+err)[-400:]}
    
    if rc == 0:
        rc2, out2, _ = sh("cd ~/llama.cpp/build && make -j4 llama-quantize llama-gguf-split 2>&1", 60)
        result["make_tools"] = {"rc": rc2, "tail": out2[-200:]}
        
        rc3, out3, _ = sh("ls -lh ~/llama.cpp/build/bin/llama-* 2>&1")
        result["bins"] = out3[:500]
        
        rc4, out4, _ = sh("~/llama.cpp/build/bin/llama-cli --version 2>&1 | head -5")
        if rc4 != 0:
            rc4, out4, _ = sh("~/llama.cpp/build/bin/llama-cli --help 2>&1 | head -3")
        result["version"] = (out4 if out4 else "unknown")[:200]

b=base64.b64encode(json.dumps(result,ensure_ascii=False).encode()).decode()
r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/llama_v2.json?access_token={T}")
try:
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"llama_v2"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/llama_v2.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15): pass
