
import json, subprocess, base64, urllib.request

T="be94810b75731a166c301f752d5348e8"
result = {}

def sh(cmd, timeout=10):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 1. rapidocr 完整 traceback（不分段）
rc, out, err = sh("python3 -c 'import rapidocr_onnxruntime' 2>&1")
result["rapidocr_trace"] = (out + "\n" + err)[:1200]

# 2. 找到 onnxruntime
rc, out, _ = sh("pip list | grep -i onnx")
result["onnx_installed"] = out[:200]

# 3. Python 3.14兼容性：试装 rapidocr 最新版
rc, out, err = sh("pip install rapidocr-onnxruntime==1.3.5 2>&1 | tail -5", 20)
result["try_1.3.5"] = (out + "\n" + err)[:300]

rc, out, err = sh("python3 -c 'from rapidocr_onnxruntime import RapidOCR; print(\"OK\")' 2>&1")
result["rapidocr_retest2"] = (out + "\n" + err)[:300]

# 4. 尝试用 tesseract 做实际微博截图测试
# 先打开微博
rc, out, _ = sh("adb shell monkey -p com.sina.weibo -c android.intent.category.LAUNCHER 1 2>&1")
import time; time.sleep(4)
rc, out, _ = sh("adb shell screencap -p /sdcard/weibo_screen.png 2>&1")
rc, out, _ = sh("tesseract /sdcard/weibo_screen.png stdout -l chi_sim+eng --psm 6 2>&1")
result["weibo_ocr"] = out[:600] if out else "EMPTY"

# 5. 当前前台
rc, out, _ = sh("adb shell dumpsys window | grep mCurrentFocus")
result["current"] = out[:200]

# 6. 检查文件是否存在
rc, out, _ = sh("ls -la /sdcard/weibo_screen.png 2>&1")
result["file_check"] = out[:200]

b=base64.b64encode(json.dumps(result,ensure_ascii=False,indent=2).encode()).decode()
try:
    r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/diag3.json?access_token={T}")
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"diag3"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/diag3.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15) as f:
    print("UPLOADED")
