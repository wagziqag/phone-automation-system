
import subprocess, json, base64, urllib.request, os
import os

T = os.environ.get("GITEE_TOKEN", "")
result = {}

def sh(cmd, timeout=15):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 1. 列出所有可执行文件
rc, out, _ = sh("ls -la ~/llama.cpp/build/bin/llama* 2>&1")
result["executables"] = out[:500]

rc, out, _ = sh("find ~/llama.cpp/build/bin/ -type f -executable 2>&1")
result["all_bins"] = out[:500]

# 2. 检查版本
rc, out, _ = sh("~/llama.cpp/build/bin/llama-cli --version 2>&1 | head -3")
if rc != 0:
    rc, out, _ = sh("~/llama.cpp/build/bin/llama-cli --help 2>&1 | head -1")
result["version"] = out[:200]

# 3. 检查现有模型
rc, out, _ = sh("find ~ -name '*.gguf' 2>/dev/null | head -20")
result["existing_gguf"] = out[:500]

# 4. 检查 huggingface_hub 或下载工具
rc, out, _ = sh("which huggingface-cli 2>&1")
result["hf_cli"] = out[:100]
rc, out, _ = sh("pip list 2>/dev/null | grep -iE 'huggingface|requests|wget'")
result["dl_tools"] = out[:200]

# 5. 磁盘空间
rc, out, _ = sh("df -h ~ 2>&1 | tail -2")
result["disk"] = out[:200]

# 6. CPU 核心数
rc, out, _ = sh("nproc 2>&1")
result["cpu_cores"] = out[:50]

b=base64.b64encode(json.dumps(result,ensure_ascii=False).encode()).decode()
r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/llama_inspect.json?access_token={T}")
try:
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"llama_inspect"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/llama_inspect.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15): pass
