
import subprocess, json, base64, urllib.request
import os

T = os.environ.get("GITEE_TOKEN", "")
result = {"tur_packages": {}, "env": {}, "poller": {}}

def sh(cmd, timeout=20):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 1. 搜索 TUR 中关键 ML 包
for pkg in ["python-torch", "python-opencv", "opencv-python", "onnxruntime", "python-onnxruntime",
            "python-numpy", "python-scipy", "python-paddlepaddle", "python-paddle",
            "transformers", "python-sentencepiece", "python-tokenizers"]:
    rc, out, _ = sh(f"pkg search {pkg} 2>&1 | head -5", 10)
    result["tur_packages"][pkg] = out[:200] if out else "not found"

# 2. 检查实际已安装的 ML 包
rc, out, _ = sh("pip list 2>/dev/null | grep -iE 'torch|onnx|cv2|opencv|transformers|funasr|paddle|rapid' | head -20", 8)
result["env"]["pip_ml"] = out[:500]

rc, out, _ = sh("pkg list-installed 2>/dev/null | grep -iE 'torch|onnx|opencv|python3-' | head -20", 8)
result["env"]["pkg_ml"] = out[:500]

# 3. 直接测试 import torch
rc, out, err = sh("python3 -c 'import torch; print(torch.__version__); print(\"CUDA:\",torch.cuda.is_available())' 2>&1", 8)
result["env"]["torch_test"] = (out+err)[:200]

# 4. 检查 poller 进程
rc, out, _ = sh("ps aux | grep -E 'poller|python3.*poll' | grep -v grep", 5)
result["poller"]["ps"] = out[:300]
rc, out, _ = sh("ls ~/phone-automation-system/poller*.py 2>&1", 5)
result["poller"]["files"] = out[:200]

# 5. 磁盘空间
rc, out, _ = sh("df -h /data 2>&1 | tail -2", 5)
result["env"]["disk"] = out[:200]

b=base64.b64encode(json.dumps(result,ensure_ascii=False).encode()).decode()
r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/tur_scan.json?access_token={T}")
try:
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"tur_scan"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/tur_scan.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15): pass
