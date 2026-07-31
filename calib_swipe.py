import subprocess,time,base64,json,urllib.request,io,sys
print("swipe_start",flush=True)
subprocess.run(["adb","shell","input","swipe","429","583","566","583","200"])
time.sleep(0.10)
raw=subprocess.run("adb exec-out screencap -p",shell=True,capture_output=True).stdout
print(f"got {len(raw)}B",flush=True)
from PIL import Image
img=Image.open(io.BytesIO(raw)).convert("RGB")
buf=io.BytesIO()
img.save(buf,format="JPEG",quality=85)
j=buf.getvalue()
b64=base64.b64encode(j).decode()
A="https://gitee.com/api/v5/repos/wagziqag/phone-automation-system"
d=json.dumps({"content":b64,"message":"c3"}).encode()
rr=urllib.request.Request(A+"/contents/screenshots/sc_c3.jpg",data=d,method="POST")
rr.add_header("Content-Type","application/json")
rr.add_header("Authorization","Bearer be94810b75731a166c301f752d5348e8")
try:
    urllib.request.urlopen(rr,timeout=60)
except:
    gr=urllib.request.Request(A+"/contents/screenshots/sc_c3.jpg")
    gr.add_header("Authorization","Bearer be94810b75731a166c301f752d5348e8")
    sha=json.loads(urllib.request.urlopen(gr).read())["sha"]
    d2=json.dumps({"content":b64,"message":"c3","sha":sha}).encode()
    r2=urllib.request.Request(A+"/contents/screenshots/sc_c3.jpg",data=d2,method="PUT")
    r2.add_header("Content-Type","application/json")
    r2.add_header("Authorization","Bearer be94810b75731a166c301f752d5348e8")
    urllib.request.urlopen(r2,timeout=60)
print("DONE",flush=True)