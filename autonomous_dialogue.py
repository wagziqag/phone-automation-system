#!/usr/bin/env python3
"""
Autonomous Dialogue Loop - Marvis ↔ 元宝 自主对话
==================================================
基于 OCR Pipeline 的闭环对话引擎:
  1. screencap 截图
  2. OCR Pipeline 提取元宝回复
  3. Gitee 上传截图 → 云端 Marvis 思考
  4. 云端返回 Marvis 回复
  5. 注入剪切板 → 元宝读取
  6. 等待元宝回复 → 回到步骤 1

CLI: python3 autonomous_dialogue.py [--max-rounds 5] [--wait 8]
"""

import subprocess as sp
import time
import sys
import os
import json
import base64
import urllib.request as ur
import re

# 项目路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from phone_system.ocr_pipeline import OCRPipeline

# ─── 配置 ───
GITEE_TOKEN = "os.environ.get("GITEE_TOKEN","")"
GITEE_OWNER = "wagziqag"
GITEE_REPO = "phone-automation-system"
API_BASE = f"https://gitee.com/api/v5/repos/{GITEE_OWNER}/{GITEE_REPO}"

SCREENSHOT_PATH = "/sdcard/yb_dialogue.png"
DIALOGUE_QUEUE = "dialogue_queue.json"     # 云端对话请求
DIALOGUE_RESULT = "dialogue_result.json"    # 云端对话回复

# 剪切板注入方式优先级
CLIPBOARD_METHODS = [
    "termux_clipboard",   # termux-clipboard-set
    "adb_keyboard",       # ADBKeyboard broadcast
    "adb_input",          # adb shell input text (英文兜底)
]

def _api_req(method, path, **kwargs):
    """Gitee API 请求"""
    url = f"{API_BASE}/contents/{path}?access_token={GITEE_TOKEN}"
    if method == "GET":
        req = ur.Request(url)
        with ur.urlopen(req, timeout=8) as f:
            return json.loads(f.read())
    elif method in ("PUT", "POST"):
        sha = kwargs.pop("sha", None)
        content = kwargs.pop("content", "")
        b64 = base64.b64encode(json.dumps(content, ensure_ascii=False).encode()).decode()
        payload = json.dumps({
            "access_token": GITEE_TOKEN,
            "content": b64,
            "message": kwargs.pop("message", "auto"),
            **(json.loads(json.dumps({"sha": sha})) if sha else {}),
        }).encode()
        req = ur.Request(f"{API_BASE}/contents/{path}", data=payload,
                         headers={"Content-Type": "application/json"}, method=method)
        with ur.urlopen(req, timeout=10) as f:
            return json.loads(f.read())

def clipboard_set(text: str) -> bool:
    """多通道剪切板写入"""
    # 方法1: termux-clipboard-set
    try:
        r = sp.run(["termux-clipboard-set", text], timeout=8, capture_output=True, text=True)
        if r.returncode == 0:
            return True
    except:
        pass

    # 方法2: ADBKeyboard broadcast
    try:
        # 用 broadcast 注入到当前焦点
        sp.run(["adb", "shell", "am", "broadcast", "-a", "ADB_INPUT_TEXT",
                "--es", "msg", text], timeout=8, capture_output=True)
        return True
    except:
        pass

    # 方法3: 备用 - 写文件然后提示
    with open("/sdcard/clipboard_fallback.txt", "w") as f:
        f.write(text)
    print(f"  [clipboard] 写入 /sdcard/clipboard_fallback.txt ({len(text)} chars)")
    return False

def post_marvis_request(screenshot_url: str, ocr_text: str) -> dict:
    """向云端 Marvis 提交对话请求，返回思考结果"""
    request = {
        "round": int(time.time()),
        "ocr_text": ocr_text,
        "screenshot_url": screenshot_url,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    sha = None
    try:
        resp = _api_req("GET", DIALOGUE_QUEUE)
        sha = resp.get("sha")
    except:
        pass
    _api_req("PUT", DIALOGUE_QUEUE, content=request, sha=sha, message=f"marvis_req")
    return request

def wait_marvis_reply(timeout: int = 30) -> dict:
    """轮询等待云端 Marvis 回复"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = _api_req("GET", DIALOGUE_RESULT)
            data = json.loads(base64.b64decode(resp["content"]).decode())
            if isinstance(data, dict) and data.get("reply"):
                return data
        except:
            pass
        time.sleep(2)
    return {"reply": "[超时] 云端未响应"}

def tap_input_area():
    """点击元宝输入框区域 (需根据实际坐标调整)"""
    # 默认点屏幕中下部，触发输入框焦点
    sp.run(["adb", "shell", "input", "tap", "540", "2100"], timeout=3, capture_output=True)
    time.sleep(0.5)

def main(max_rounds: int = 5, wait_between: int = 8):
    pipe = OCRPipeline()
    print("=" * 60)
    print(f"Autonomous Dialogue | max_rounds={max_rounds} | wait={wait_between}s")
    print("=" * 60)

    for rnd in range(1, max_rounds + 1):
        print(f"\n--- Round {rnd}/{max_rounds} ---")

        # 1. 截图
        print("  [1/5] screencap...")
        sp.run(["screencap", "-p", SCREENSHOT_PATH], timeout=5)

        # 2. OCR 提取
        print("  [2/5] OCR pipeline...")
        t0 = time.time()
        ocr_res = pipe.run(SCREENSHOT_PATH, upload=True)
        ocr_text = ""
        if ocr_res.all_schemes.get("scheme1_raw") and ocr_res.all_schemes["scheme1_raw"].ok:
            ocr_text = ocr_res.all_schemes["scheme1_raw"].text
        print(f"       [{int((time.time()-t0)*1000)}ms] {len(ocr_text)} chars extracted")

        # 3. 获取截图URL (从 scheme4)
        ss_url = ""
        s4 = ocr_res.all_schemes.get("scheme4_cloud")
        if s4 and s4.ok:
            ss_url = s4.preprocess.replace("Gitee POST → ", "")

        # 4. 向云端提交请求
        print("  [3/5] post to cloud...")
        post_marvis_request(ss_url, ocr_text)

        # 5. 等待云端回复 (这里由外部 Marvis 通过对话处理)
        print(f"  [4/5] waiting cloud reply (max 30s)...")
        reply = wait_marvis_reply(timeout=30)

        if reply.get("reply"):
            marvis_text = reply["reply"]
            print(f"  Marvis: {marvis_text[:100]}...")

            # 6. 注入剪切板 → 元宝
            print("  [5/5] injecting clipboard...")
            tap_input_area()
            clipboard_set(marvis_text)
            print("       done")
        else:
            print("  [!] no reply from cloud, skipping")

        if rnd < max_rounds:
            print(f"  waiting {wait_between}s for 元宝...")
            time.sleep(wait_between)

    print("\n=== Dialogue ended ===")

if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(rounds, wait)
