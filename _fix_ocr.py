import json, os, subprocess, base64, urllib.request, sys
import os

T=os.environ.get("GITEE_TOKEN", "")
result = {}

def sh(cmd, timeout=30):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 1. 修复 rapidocr - 看具体报错
rc, out, err = sh("python3 -c 'from rapidocr_onnxruntime import RapidOCR' 2>&1", 10)
result["rapidocr_err"] = (out + "\n" + err)[:600]

# 2. 尝试安装 paddlex
rc, out, err = sh("pip install paddlex 2>&1 | tail -5", 60)
result["install_paddlex"] = (out + "\n" + err)[:400]

# 3. 如果paddlex装不上，试pip install paddlepaddle
if "ERROR" in out or "error" in out.lower():
    rc, out, err = sh("pip install paddlepaddle 2>&1 | tail -5", 60)
    result["install_paddlepaddle"] = (out + "\n" + err)[:400]

# 4. 检查 tesseract 版本
rc, out, _ = sh("tesseract --version 2>&1 | head -3")
result["tesseract"] = out[:300]

# 5. 检查已安装语言包
rc, out, _ = sh("tesseract --list-langs 2>&1")
result["tesseract_langs"] = out[:300]

# 6. 测试 tesseract 对微博风格文字
rc, out, _ = sh("echo '这是一条微博评论测试内容' | tesseract stdin stdout -l chi_sim 2>&1")
result["tesseract_test"] = out[:200]

# 7. 找到微博的主Activity
rc, out, _ = sh("adb shell dumpsys package com.sina.weibo | grep -E '^\s+[a-f0-9]+ com.sina.weibo/' | head -20", 5)
result["weibo_activities_full"] = out[:800]

# 8. 获取微博版本
rc, out, _ = sh("adb shell dumpsys package com.sina.weibo | grep versionName", 5)
result["weibo_version"] = out[:200]

# 上传
b=base64.b64encode(json.dumps(result,ensure_ascii=False,indent=2).encode()).decode()
try:
    r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/diag_fix.json?access_token={T}")
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"fix"}
if sha: pl["sha"]=sha
verb="PUT" if sha else "POST"
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/diag_fix.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method=verb)
with urllib.request.urlopen(req,timeout=15) as f:
    print("FIX_UPLOADED", json.loads(f.read())['content']['sha'][:12])
