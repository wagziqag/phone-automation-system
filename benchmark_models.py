#!/usr/bin/env python3
"""Ollama 本地模型基准测试 —— 测试视觉/文本能力，选出最适合手机助手的模型。"""

import json
import time
import base64
import io
import sys
import os
import requests


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
TIMEOUT = 120

# 用于视觉测试的 1x1 白色 PNG
DUMMY_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

# 视觉测试 prompt（要求输出 JSON）
VISION_PROMPT = """你看到了什么？请用中文简要描述屏幕内容，然后给出下一步操作建议。
严格返回 JSON 格式:
{"observation": "简要描述", "action": "done", "reason": "原因"}"""

# 文本测试 prompt
TEXT_PROMPT = """将以下目标分解为操作步骤:
目标: 打开抖音搜索猫咪视频
严格返回 JSON:
{"plan": [{"step": 1, "action": "launch", "package": "com.ss.android.ugc.aweme", "reason": "打开抖音"}, {"step": 2, "action": "tap", "x": 540, "y": 200, "reason": "点击搜索框"}], "estimated_steps": 2}"""


def list_models(session):
    """列出本地所有模型。"""
    try:
        with session.get(f"{OLLAMA_URL}/api/tags", timeout=10) as resp:
            if resp.status == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        print(f"  [错误] 无法连接 Ollama: {e}")
    return []


def test_vision(session, model):
    """测试视觉能力：发送图片看是否支持多模态。"""
    start = time.time()
    try:
        with session.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": VISION_PROMPT,
                "images": [DUMMY_IMAGE],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 200},
            },
            timeout=TIMEOUT,
        ) as resp:
            elapsed = time.time() - start

            if resp.status != 200:
                raw = resp.text()
                if "multimodal" in raw.lower() or "does not support" in raw.lower():
                    return {"vision_ok": False, "reason": "不支持多模态", "elapsed": elapsed}
                return {"vision_ok": False, "reason": f"HTTP {resp.status}: {raw[:80]}", "elapsed": elapsed}

            data = resp.json()
            response = data.get("response", "")

            # 验证 JSON 格式
            try:
                _extract_and_parse(response)
                json_ok = True
            except Exception:
                json_ok = False

            return {
                "vision_ok": True,
                "elapsed": round(elapsed, 2),
                "json_ok": json_ok,
                "response_preview": response[:120].replace("\n", " "),
                "tokens": data.get("eval_count", 0),
            }
    except Exception as e:
        elapsed = time.time() - start
        return {"vision_ok": False, "reason": str(e)[:80], "elapsed": round(elapsed, 2)}


def test_text_json(session, model):
    """测试文本模型的 JSON 格式遵从性。"""
    start = time.time()
    try:
        with session.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": TEXT_PROMPT,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 300},
            },
            timeout=TIMEOUT,
        ) as resp:
            elapsed = time.time() - start
            if resp.status != 200:
                return {"text_ok": False, "reason": f"HTTP {resp.status}", "elapsed": round(elapsed, 2)}

            data = resp.json()
            response = data.get("response", "")

            try:
                parsed = _extract_and_parse(response)
                json_ok = True
                has_plan = "plan" in parsed
            except Exception:
                json_ok = False
                has_plan = False

            return {
                "text_ok": True,
                "elapsed": round(elapsed, 2),
                "json_ok": json_ok,
                "has_plan": has_plan,
                "tokens": data.get("eval_count", 0),
            }
    except Exception as e:
        elapsed = time.time() - start
        return {"text_ok": False, "reason": str(e)[:80], "elapsed": round(elapsed, 2)}


def _extract_and_parse(text):
    """提取并解析 JSON。"""
    import re
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return json.loads(m.group(1).strip())
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group(0).strip())
    return json.loads(text)


def main():
    print("=" * 55)
    print("  Ollama 本地模型基准测试")
    print("=" * 55)
    print(f"  Ollama URL: {OLLAMA_URL}")
    print()

    with requests.Session() as session:
        models = list_models(session)
        if not models:
            print("[失败] 未找到本地模型。请先 ollama pull <model> 拉取模型。")
            return

        print(f"  本地模型 ({len(models)} 个):")
        for m in models:
            print(f"    - {m}")
        print()

        results = {}
        vision_candidates = []

        for model in models:
            print(f"  测试: {model}")
            print(f"    ├─ 视觉能力...", end=" ", flush=True)
            vis = test_vision(session, model)
            if vis["vision_ok"]:
                tag = "OK" if vis["json_ok"] else "NO_JSON"
                print(f"{tag} ({vis['elapsed']}s, {vis.get('tokens',0)} tokens)")
                print(f"    │  {vis['response_preview'][:80]}")
                vision_candidates.append((model, vis))
            else:
                print(f"FAIL ({vis.get('reason', '?')})")

            print(f"    └─ 文本JSON...", end=" ", flush=True)
            txt = test_text_json(session, model)
            if txt["text_ok"]:
                tag = "OK" if txt["json_ok"] else "NO_JSON"
                print(f"{tag} ({txt['elapsed']}s, {txt.get('tokens',0)} tokens)")
            else:
                print(f"FAIL ({txt.get('reason','?')})")

            results[model] = {"vision": vis, "text": txt}
            print()

        # 推荐
        print("=" * 55)
        print("  推荐结果")
        print("=" * 55)

        if not vision_candidates:
            print()
            print("  [警告] 没有发现支持多模态(视觉)的模型！")
            print("  手机助手需要视觉模型来分析屏幕截图。")
            print("  推荐拉取以下之一:")
            print("    ollama pull minicpm-v:latest      (~8B, 推荐)")
            print("    ollama pull llava:7b              (~7B)")
            print("    ollama pull llava-phi3:latest     (~3.8B, 轻量)")
            print("    ollama pull moondream:latest      (~1.8B, 极速)")
            print()
        else:
            # 按速度+JSON遵从性排序
            vision_candidates.sort(key=lambda x: (not x[1]["json_ok"], x[1]["elapsed"]))
            print()
            print(f"  {'模型':<35} {'视觉':>6} {'JSON':>6} {'耗时':>8}")
            print(f"  {'-'*35} {'-'*6} {'-'*6} {'-'*8}")
            for model, vis in vision_candidates:
                json_str = "OK" if vis["json_ok"] else "FAIL"
                print(f"  {model:<35} {'OK':>6} {json_str:>6} {vis['elapsed']:>7.1f}s")

            best = vision_candidates[0]
            print()
            print(f"  [推荐] 视觉模型: {best[0]}")
            print(f"         速度: {best[1]['elapsed']}s, JSON: {'OK' if best[1]['json_ok'] else '需优化'}")
            print()

            # 检查是否有更快的文本模型可做 fallback
            text_models = [
                (m, r["text"])
                for m, r in results.items()
                if r["text"].get("text_ok") and r["text"].get("json_ok")
            ]
            if text_models:
                text_models.sort(key=lambda x: x[1]["elapsed"])
                best_text = text_models[0]
                if best_text[0] != best[0]:
                    print(f"  [提示] 文本模型可选 {best_text[0]} ({best_text[1]['elapsed']}s) 作为非视觉任务的 fallback")
                    print()

        # 更新配置文件（可选）
        print("  ---")
        if vision_candidates:
            best_model = vision_candidates[0][0]
            config_path = os.path.expanduser("~/.phone-assistant/termux_config.json")
            try:
                if os.path.exists(config_path):
                    with open(config_path) as f:
                        config = json.load(f)
                    config["vision_model"] = best_model
                    config["model_name"] = best_model
                    with open(config_path, "w") as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                    print(f"  [已更新] termux_config.json → vision_model: {best_model}")
                else:
                    print(f"  [跳过] 配置文件不存在: {config_path}")
            except Exception as e:
                print(f"  [失败] 更新配置时出错: {e}")
        print()


if __name__ == "__main__":
    (main())
