
import json, os, os, subprocess, base64, urllib.request
import os

T=os.environ.get("GITEE_TOKEN","")

def sh(cmd):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() + "\n" + r.stderr.strip()
    except: return "TIMEOUT"

result = {}

# 1. PaddleOCR
result["paddleocr"] = sh('python3 -c "import paddleocr; print(paddleocr.__version__)" 2>&1')[:500]

# 2. RapidOCR
result["rapidocr"] = sh('python3 -c "from rapidocr_onnxruntime import RapidOCR; print(dir(RapidOCR))" 2>&1')[:500]

# 3. pip list
result["pip_ocr"] = sh("pip list 2>/dev/null | grep -iE 'ocr|onnx|paddle|rapid' | head -10")[:500]

# 4. CPU
result["cpu"] = sh("cat /proc/cpuinfo | grep -E 'processor|BogoMIPS|Hardware' | head -12")[:500]

# 5. Weibo activities
result["weibo_activities"] = sh("adb shell dumpsys package com.sina.weibo | grep -iE 'Activity|activity' | grep -v 'Permission\|Intent\|Action' | head -20")[:800]

# 6. Python version
result["python_version"] = sh("python3 --version")[:100]

# 上传
b=base64.b64encode(json.dumps(result,ensure_ascii=False,indent=2).encode()).decode()
try:
    r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/diag_weibo.json?access_token={T}")
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"diag"}
if sha: pl["sha"]=sha
verb="PUT" if sha else "POST"
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/diag_weibo.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method=verb)
with urllib.request.urlopen(req,timeout=15) as f:
    print("DIAG_UPLOADED", json.loads(f.read())['content']['sha'][:12])
