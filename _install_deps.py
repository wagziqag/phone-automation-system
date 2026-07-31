import subprocess, json, base64, urllib.request
import os

T=os.environ.get("GITEE_TOKEN", "")
result = {}

for pkg in ["opencv-python-headless", "onnxruntime"]:
    try:
        r = subprocess.run(f"pip install {pkg} --no-deps 2>&1 | tail -5", shell=True, capture_output=True, text=True, timeout=45)
        result[pkg] = {"rc": r.returncode, "out": r.stdout.strip()[:300]}
    except Exception as e:
        result[pkg] = {"rc": -1, "out": str(e)[:200]}

# 试试用 apt 装 python3-opencv
try:
    r = subprocess.run("pkg list-installed 2>/dev/null | grep -i opencv", shell=True, capture_output=True, text=True, timeout=10)
    result["pkg_opencv"] = r.stdout.strip()[:200]
except: result["pkg_opencv"] = "failed"

b=base64.b64encode(json.dumps(result,ensure_ascii=False).encode()).decode()
r=urllib.request.Request(f"https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/dep_install.json?access_token={T}")
try:
    with urllib.request.urlopen(r,timeout=8) as f:
        sha=json.loads(f.read()).get("sha") if isinstance(json.loads(f.read()),dict) else None
except: sha=None
pl={"access_token":T,"content":b,"message":"dep_install"}
if sha: pl["sha"]=sha
req=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/dep_install.json",
    data=json.dumps(pl).encode(),
    headers={"Content-Type":"application/json;charset=UTF-8"}, method="PUT" if sha else "POST")
with urllib.request.urlopen(req,timeout=15): pass
