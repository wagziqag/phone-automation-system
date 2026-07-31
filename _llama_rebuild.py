
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

# Step 0: 检查当前 remote
rc, out, _ = sh("cd ~/llama.cpp && git remote -v 2>&1 | head -5")
result["remote"] = out[:300]

# Step 1: 更新仓库
result["stage"] = "git_pull"
rc, out, err = sh("cd ~/llama.cpp && git pull origin main 2>&1", 30)
if rc != 0:
    rc, out, err = sh("cd ~/llama.cpp && git pull origin master 2>&1", 30)
result["git_pull"] = {"rc": rc, "out": (out+err)[:400]}

# Step 2: 清理旧 build
result["stage"] = "clean_build"
rc, out, _ = sh("rm -rf ~/llama.cpp/build && mkdir -p ~/llama.cpp/build", 5)
result["clean"] = rc

# Step 3: cmake 配置
result["stage"] = "cmake"
rc, out, err = sh("cd ~/llama.cpp/build && cmake .. -DGGML_CPU_ALL_VARIANTS=ON -DGGML_NATIVE=OFF -DLLAMA_CURL=ON 2>&1", 60)
result["cmake"] = {"rc": rc, "out": (out+err)[-500:]}

# Step 4: make 编译（只编译关键目标，加快速度）
if rc == 0:
    result["stage"] = "make"
    # 先编译 llama-cli
    rc, out, err = sh("cd ~/llama.cpp/build && make -j4 llama-cli 2>&1", 120)
    result["make_llama_cli"] = {"rc": rc, "out": (out+err)[-400:]}
    
    if rc == 0:
        # 顺便编译其他常用工具
        rc2, out2, _ = sh("cd ~/llama.cpp/build && make -j4 llama-server llama-quantize llama-gguf-split 2>&1", 120)
        result["make_others"] = {"rc": rc2, "out": out2[-300:]}
        
        # 验证
        rc3, out3, _ = sh("ls -la ~/llama.cpp/build/bin/llama-* 2>&1")
        result["final_bins"] = out3[:500]
        
        # 版本
        rc4, out4, _ = sh("~/llama.cpp/build/bin/llama-cli --version 2>&1 | head -5")
        if rc4 != 0:
            rc4, out4, _ = sh("~/llama.cpp/build/bin/llama-cli --help 2>&1 | head -3")
        result["version"] = out4[:200]

b=base64.b64encode(json.dumps(result,ensure_ascii=False).encode()).decode()
r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/llama_rebuild.json?access_token={T}")
try:
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"llama_rebuild"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/llama_rebuild.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15): pass
