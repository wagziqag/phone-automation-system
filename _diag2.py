
import json, os, subprocess, base64, urllib.request

T="be94810b75731a166c301f752d5348e8"
result = {}

def sh(cmd, timeout=15):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 1. rapidocr 完整报错
rc, out, err = sh("python3 -c 'from rapidocr_onnxruntime import RapidOCR' 2>&1")
result["rapidocr_full"] = (out + "\n" + err)[:600]

# 2. 尝试重装 rapidocr + onnxruntime
rc, out, err = sh("pip install --upgrade rapidocr-onnxruntime onnxruntime 2>&1 | tail -8", 30)
result["reinstall_rapidocr"] = out[:400]

# 3. re-test rapidocr after reinstall
rc, out, err = sh("python3 -c 'from rapidocr_onnxruntime import RapidOCR; print(\"OK\")' 2>&1")
result["rapidocr_retest"] = (out + "\n" + err)[:300]

# 4. tesseract 测试 - 用实际微博截图风格文字
# 截图微博帖子
rc, out, _ = sh("adb shell screencap -p /sdcard/weibo_test.png")
# OCR 
rc, out, _ = sh("tesseract /sdcard/weibo_test.png stdout -l chi_sim+eng --psm 6 2>&1")
result["weibo_ocr_test"] = out[:500] if out else "EMPTY"

# 5. 截图分辨率
rc, out, _ = sh("adb shell wm size")
result["screen_size"] = out[:100]

# 6. 当前前台app
rc, out, _ = sh("adb shell dumpsys window | grep mCurrentFocus")
result["current_app"] = out[:200]

# 7. 获取微博版本号
rc, out, _ = sh("adb shell dumpsys package com.sina.weibo | grep -E 'versionName'")
result["weibo_version"] = out[:200]

b=base64.b64encode(json.dumps(result,ensure_ascii=False,indent=2).encode()).decode()
try:
    r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/diag2.json?access_token={T}")
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"diag2"}
if sha: pl["sha"]=sha
verb="PUT" if sha else "POST"
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/diag2.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method=verb)
with urllib.request.urlopen(req,timeout=15) as f:
    print("DIAG2_UPLOADED")
