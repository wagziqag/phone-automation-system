
import subprocess, json, base64, urllib.request
import os

T = os.environ.get("GITEE_TOKEN", "")
result = {}

def sh(cmd, timeout=12):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 检查是否有 pip list moss
rc, out, _ = sh("pip list 2>/dev/null | grep -iE 'moss|tts|transformers|llama'", 8)
result["pip_related"] = out[:300]

# 检查 ffmpeg
rc, out, _ = sh("which ffmpeg && ffmpeg -version 2>&1 | head -1")
result["ffmpeg"] = out[:100]

rc, out, _ = sh("which cmake && cmake --version 2>&1 | head -1")
result["cmake"] = out[:100]

# 检查 transformers 版本
rc, out, _ = sh("python3 -c 'import transformers; print(transformers.__version__)' 2>&1")
result["transformers"] = (out if out else "NOT INSTALLED")[:100]

# onnxruntime
rc, out, _ = sh("python3 -c 'import onnxruntime; print(onnxruntime.__version__)' 2>&1")
result["onnxruntime"] = (out if out else "NOT INSTALLED")[:100]

b=base64.b64encode(json.dumps(result,ensure_ascii=False).encode()).decode()
r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/moss_env.json?access_token={T}")
try:
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"moss_env"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/moss_env.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15): pass
