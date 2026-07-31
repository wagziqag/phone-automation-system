
import json, os, subprocess, base64, urllib.request
import os

T = os.environ.get("GITEE_TOKEN", "")
result = {}

def sh(cmd, timeout=60):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 1. 安装 opencv-python-headless
rc, out, err = sh("pip install opencv-python-headless 2>&1 | tail -10", 60)
result["install_cv2"] = (out + "\n" + err)[:500]

# 2. 测试 rapidocr
rc, out, err = sh("python3 -c 'from rapidocr_onnxruntime import RapidOCR; print(\"RapidOCR OK\")' 2>&1")
result["rapidocr_test"] = (out + "\n" + err)[:300]

# 3. 如果 rapidocr 还不行，试装 opencv-python（带GUI的版本）
if "OK" not in (out + err):
    rc, out, err = sh("pip install opencv-python 2>&1 | tail -5", 30)
    result["install_cv2_full"] = (out + "\n" + err)[:300]
    rc, out, err = sh("python3 -c 'from rapidocr_onnxruntime import RapidOCR; print(\"RapidOCR OK\")' 2>&1")
    result["rapidocr_test2"] = (out + "\n" + err)[:300]

# 4. 最终OCR引擎状态
rc, out, _ = sh("python3 -c 'import tesserocr; print(\"tesserocr OK\")' 2>&1 || python3 -c 'import pytesseract; print(\"pytesseract OK\")' 2>&1 || echo 'no python tesseract wrapper'")
result["tesseract_wrapper"] = out[:200]

# 5. 如果 rapidocr 还是不行，尝试用 pip install --force-reinstall
if "OK" not in (out + err):
    # 卸载重装
    sh("pip uninstall -y rapidocr-onnxruntime 2>&1", 8)
    rc, out, err = sh("pip install rapidocr-onnxruntime 2>&1 | tail -8", 30)
    result["reinstall_rapid"] = (out + "\n" + err)[:400]
    rc, out, err = sh("python3 -c 'from rapidocr_onnxruntime import RapidOCR; print(\"RapidOCR OK\")' 2>&1")
    result["rapidocr_final"] = (out + "\n" + err)[:300]

b=base64.b64encode(json.dumps(result,ensure_ascii=False,indent=2).encode()).decode()
try:
    r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/fix_cv2.json?access_token={T}")
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"fix_cv2"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/fix_cv2.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15) as f:
    print("UPLOADED")
