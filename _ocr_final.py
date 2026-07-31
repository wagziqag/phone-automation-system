
import json, subprocess, base64, urllib.request, os
import os

T = os.environ.get("GITEE_TOKEN", "")
result = {}

def sh(cmd, timeout=30):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 1. pkg 搜索 opencv
rc, out, _ = sh("pkg search opencv 2>&1 | head -10")
result["pkg_opencv"] = out[:300]

# 2. 已有 cv2 检查
rc, out, _ = sh("python3 -c 'import cv2; print(cv2.__version__)' 2>&1")
result["cv2_check"] = out[:200]

# 3. 尝试通过 pkg 安装 opencv
if "ModuleNotFoundError" in result.get("cv2_check",""):
    rc, out, err = sh("pkg install -y opencv 2>&1 | tail -10", 40)
    result["pkg_install"] = (out + "\n" + err)[:400]
    # 重新检查
    rc, out, _ = sh("python3 -c 'import cv2; print(cv2.__version__)' 2>&1")
    result["cv2_post_pkg"] = out[:200]

# 4. 尝试安装 paddlex (PaddleOCR依赖)
rc, out, err = sh("pip install paddlex 2>&1 | tail -8", 60)
result["paddlex_install"] = (out + "\n" + err)[:500]

# 5. 测试 PaddleOCR after paddlex install
rc, out, err = sh("python3 -c 'from paddleocr import PaddleOCR; print(\"PaddleOCR OK\")' 2>&1")
result["paddleocr_post"] = (out + "\n" + err)[:400]

# 6. 测试 rapidocr after pkg opencv
rc, out, err = sh("python3 -c 'from rapidocr_onnxruntime import RapidOCR; print(\"RapidOCR OK\")' 2>&1")
result["rapidocr_post"] = (out + "\n" + err)[:400]

# 7. tesseract 基准
rc, out, _ = sh("tesseract --list-langs 2>&1")
result["tesseract_langs"] = out[:300]

# 8. Python 的 ocr 包
rc, out, _ = sh("python3 -c 'import pytesseract; print(pytesseract.__version__)' 2>&1")
result["pytesseract"] = out[:200]

b=base64.b64encode(json.dumps(result,ensure_ascii=False,indent=2).encode()).decode()
try:
    r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/ocr_final.json?access_token={T}")
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"ocr_final"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/ocr_final.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15) as f:
    print("UPLOADED")
