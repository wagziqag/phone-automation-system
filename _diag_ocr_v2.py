
import json, os, subprocess, base64, urllib.request, os
import os

T=os.environ.get("GITEE_TOKEN","")
result = {}

def sh(cmd, timeout=12):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"

# 精确判定每个引擎
tests = [
    ("tesseract_cli", "tesseract --list-langs 2>&1", "chi_sim" if None else None),
    ("pytesseract", "python3 -c 'import pytesseract; print(\"OK\",pytesseract.get_languages())' 2>&1", "OK"),
    ("paddleocr", "python3 -c 'from paddleocr import PaddleOCR; print(\"OK\")' 2>&1", "OK"),
    ("rapidocr_onnx", "python3 -c 'from rapidocr_onnxruntime import RapidOCR; engine=RapidOCR(); print(\"OK\")' 2>&1", "OK"),
    ("easyocr", "python3 -c 'import easyocr; print(\"OK\", easyocr.__version__)' 2>&1", "OK"),
    ("surya_ocr", "python3 -c 'from surya.ocr import run_ocr; print(\"OK\")' 2>&1", "OK"),
    ("doctr", "python3 -c 'import os; os.environ[\"USE_TF\"]=\"0\"; from doctr.models import ocr_predictor; print(\"OK\")' 2>&1", "OK"),
    ("trocr", "python3 -c 'from transformers import TrOCRProcessor, VisionEncoderDecoderModel; print(\"OK\")' 2>&1", "OK"),
    ("chineseocr_lite", "python3 -c 'from chineseocr_lite.model import OcrHandle; print(\"OK\")' 2>&1", "OK"),
    ("cnocr", "python3 -c 'from cnocr import CnOcr; ocr=CnOcr(); print(\"OK\")' 2>&1", "OK"),
]

for name, cmd, keyword in tests:
    rc, out, err = sh(cmd, 15)
    combined = out + "\n" + err
    if keyword:
        ok = keyword in combined
    else:
        ok = rc == 0 and "chi_sim" in combined
    result[name] = {"ok": ok, "rc": rc, "preview": combined[:250]}

# pip install 可行性检测
rc, out, _ = sh("pip install --dry-run 2>&1 | head -5")
result["pip_working"] = True if rc == 0 or "Usage" in str(out) else False

# 检查 cv2 / onnx / torch 具体错误
rc, out, _ = sh("python3 -c 'import cv2' 2>&1")
result["cv2_error"] = out[:120] if "ModuleNotFoundError" in out else ""
rc, out, _ = sh("python3 -c 'import onnxruntime' 2>&1")
result["onnx_error"] = out[:120] if "ModuleNotFoundError" in out else ""

b=base64.b64encode(json.dumps(result,ensure_ascii=False,indent=2).encode()).decode()
r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/ocr_diag_v2.json?access_token={T}")
try:
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"ocr_diag"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/ocr_diag_v2.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15): pass
