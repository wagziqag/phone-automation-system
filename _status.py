
import subprocess, json, base64, urllib.request
import os
T = os.environ.get("GITEE_TOKEN", "")
def sh(cmd, t=10):
    try:
        r=subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except: return -1, "", "TIMEOUT"
result={}
rc,out,_=sh("ls -lh ~/llama.cpp/build/bin/llama-* 2>&1")
result["bins"]=out[:500]
rc,out,_=sh("cd ~/llama.cpp && git log --oneline -3 2>&1")
result["git_log"]=out[:200]
rc,out,_=sh("cd ~/llama.cpp && git remote -v")
result["remote"]=out[:200]
rc,out,_=sh("ps aux | grep -E 'cmake|make|cc1|cc1plus' | grep -v grep | head -5")
result["running_procs"]=out[:300]
b=base64.b64encode(json.dumps(result,ensure_ascii=False).encode()).decode()
pl={"access_token":T,"content":b,"message":"status"}
r=urllib.request.Request("https://gitee.com/api/v5/repos/wagziqag/phone-automation-system/contents/status_check.json",data=json.dumps(pl).encode(),headers={"Content-Type":"application/json;charset=UTF-8"},method="PUT")
try:
    with urllib.request.urlopen(r,timeout=10): pass
except: pass
