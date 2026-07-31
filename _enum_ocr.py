
import json, os, subprocess, base64, urllib.request, os, sys
import os

T=os.environ.get("GITEE_TOKEN","")
result = {"ocr_engines": {}, "system": {}}

def sh(cmd, timeout=15):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 0. 基础环境
rc, out, _ = sh("python3 --version")
result["system"]["python"] = out[:50]
rc, out, _ = sh("uname -m")
result["system"]["arch"] = out[:50]
rc, out, _ = sh("pip list 2>/dev/null | wc -l")
result["system"]["pip_packages"] = out[:20]

# 检查每个OCR引擎
engines = [
    ("tesseract_cli", "which tesseract && tesseract --version 2>&1 | head -2"),
    ("pytesseract", "python3 -c 'import pytesseract; print(pytesseract.__version__)' 2>&1"),
    ("paddleocr", "python3 -c 'import paddleocr; print(paddleocr.__version__)' 2>&1"),
    ("rapidocr_onnx", "python3 -c 'from rapidocr_onnxruntime import RapidOCR; print(\"import_ok\")' 2>&1"),
    ("easyocr", "python3 -c 'import easyocr; print(easyocr.__version__)' 2>&1"),
    ("surya_ocr", "python3 -c 'from surya.ocr import run_ocr; print(\"import_ok\")' 2>&1"),
    ("doctr", "python3 -c 'from doctr.models import ocr_predictor; print(\"import_ok\")' 2>&1"),
    ("trocr", "python3 -c 'from transformers import TrOCRProcessor; print(\"import_ok\")' 2>&1"),
    ("chineseocr_lite", "python3 -c 'from chineseocr_lite.model import OcrHandle; print(\"import_ok\")' 2>&1"),
    ("cnocr", "python3 -c 'from cnocr import CnOcr; print(\"import_ok\")' 2>&1"),
]

for name, cmd in engines:
    rc, out, err = sh(cmd, 10)
    result["ocr_engines"][name] = {
        "available": "import_ok" in (out+err).lower() or "version" in (out+err).lower() or "tesseract" in (out+err).lower(),
        "output": (out + "\n" + err)[:300]
    }

# 尝试 import cv2
rc, out, err = sh("python3 -c 'import cv2; print(cv2.__version__)' 2>&1")
result["system"]["cv2"] = out[:100] if out else err[:100]

# 尝试 import onnxruntime
rc, out, err = sh("python3 -c 'import onnxruntime; print(onnxruntime.__version__)' 2>&1")
result["system"]["onnxruntime"] = out[:100] if out else err[:100]

# 尝试 import torch
rc, out, err = sh("python3 -c 'import torch; print(torch.__version__)' 2>&1")
result["system"]["torch"] = (out if out else err)[:100]

# 可用内存/存储
rc, out, _ = sh("free -h 2>&1 | head -3")
result["system"]["memory"] = out[:200]
rc, out, _ = sh("df -h /data 2>&1 | tail -2")
result["system"]["storage"] = out[:200]

b=base64.b64encode(json.dumps(result,ensure_ascii=False,indent=2).encode()).decode()
try:
    r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/ocr_enum.json?access_token={T}")
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"ocr_enum"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/ocr_enum.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15) as f:
    print("UPLOADED")
