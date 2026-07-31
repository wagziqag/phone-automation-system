#!/usr/bin/env python3
"""
bootstrap.py — 统一引导入口

自动检测运行环境，启动合适的 Agent 组件：
  - ZeroTermux + ADB/Shizuku → phone_agent (交互/daemon)
  - ZeroTermux 无 ADB       → search_agent + file_agent
  - 任意 Linux 环境         → search_agent + 工具链
  - Docker / CI             → 测试模式

用法:
  python bootstrap.py                  # 自动检测并启动
  python bootstrap.py --mode marvis    # 强制 Marvis 调度模式
  python bootstrap.py --mode cli       # 强制原 CLI 模式
  python bootstrap.py --status         # 仅显示环境状态
"""

from __future__ import annotations

import argparse
import json
# asyncio removed (sync mode)
import os
import platform
import subprocess
import sys
from pathlib import Path

# ── 确保项目在 sys.path ──
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))


def detect_environment() -> dict:
    """全面检测运行环境。"""
    env = {
        "platform": "unknown",
        "is_termux": False,
        "has_adb": False,
        "has_shizuku": False,
        "has_ollama": False,
        "python_version": platform.python_version(),
        "project_dir": str(PROJECT_DIR),
    }

    # Termux 检测
    if "com.termux" in os.environ.get("PREFIX", ""):
        env["is_termux"] = True
        env["platform"] = "termux"
    elif "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
        env["is_termux"] = True
        env["platform"] = "termux"
    else:
        env["platform"] = platform.system().lower()

    # ADB 检测
    try:
        r = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            env["has_adb"] = True
            # 检查是否有设备
            r2 = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
            devices = [l for l in r2.stdout.split("\n") if "device" in l and "devices" not in l]
            env["adb_devices"] = len(devices)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        env["has_adb"] = False

    # Shizuku 检测
    try:
        r = subprocess.run(
            ["adb", "shell", "sh", "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh", "status"],
            capture_output=True, text=True, timeout=5
        )
        env["has_shizuku"] = "running" in r.stdout.lower()
    except Exception:
        env["has_shizuku"] = False

    # Ollama 检测
    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        import urllib.request
        urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=3)
        env["has_ollama"] = True
        env["ollama_url"] = ollama_url
    except Exception:
        env["has_ollama"] = False

    return env


def print_status(env: dict):
    """格式化输出环境状态。"""
    status_symbols = {True: "✓", False: "✗"}

    try:
        from rich.table import Table
        from rich.console import Console
        console = Console()
        table = Table(title="📱 Phone Automation System v2.0")
        table.add_column("项目", style="cyan")
        table.add_column("状态")
        table.add_row("平台", env["platform"])
        table.add_row("Python", env["python_version"])
        table.add_row("Termux", status_symbols[env["is_termux"]])
        table.add_row("ADB", f"{status_symbols[env['has_adb']]} (设备: {env.get('adb_devices', 0)})")
        table.add_row("Shizuku", status_symbols[env["has_shizuku"]])
        table.add_row("Ollama", f"{status_symbols[env['has_ollama']]} ({env.get('ollama_url', 'N/A')})")
        console.print(table)
    except ImportError:
        print("=" * 60)
        print("Phone Automation System v2.0")
        print("=" * 60)
        print(f"  平台    : {env['platform']}")
        print(f"  Python  : {env['python_version']}")
        print(f"  Termux  : {status_symbols[env['is_termux']]}")
        print(f"  ADB     : {status_symbols[env['has_adb']]} (设备: {env.get('adb_devices', 0)})")
        print(f"  Shizuku : {status_symbols[env['has_shizuku']]}")
        print(f"  Ollama  : {status_symbols[env['has_ollama']]}")
        print("=" * 60)


def start_marvis(env: dict):
    """启动 Marvis Agent 调度框架。"""
    from marvis_orchestrator import VERSION
    print(f"\nMarvis Agent 调度框架 v{VERSION} 启动中...")

    from marvis_orchestrator.hub import MarvisHub

    ollama_url = env.get("ollama_url", "http://127.0.0.1:11434")
    workspace = str(Path.home() / ".marvis")

    hub = MarvisHub(
        ollama_url=ollama_url,
        workspace=workspace,
    )

    init_status = hub.init(connect_adb=env.get("has_adb", False))

    print(f"  Ollama: {'✓' if init_status.get('ollama') else '✗'}")
    print(f"  手机:   {'✓' if init_status.get('phone_connected') else '✗'}")

    # 进入交互循环
    print("\n输入自然语言指令，exit 退出")
    print("-" * 40)

    try:
        while True:
            try:
                user_input = input("Marvis> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                break
            if user_input.lower() in ("status", "st"):
                print_status(detect_environment())
                continue
            if user_input.lower() in ("help", "h", "?"):
                print("命令: <自然语言> | search <关键词> | status | exit")
                continue

            if user_input.lower().startswith("search "):
                query = user_input[7:]
                result = hub.search_agent.search_and_summarize(query)
                print(f"\n{result.get('summary', result)}")
            else:
                result = hub.dispatch(user_input)
                res = result.get("result", result)
                if isinstance(res, dict):
                    summary = res.get("summary", res.get("observation", ""))
                    if summary:
                        print(f"\n{summary[:500]}")
                    elif res.get("files"):
                        print(f"共 {res.get('total', 0)} 个文件")
                    elif res.get("error"):
                        print(f"错误: {res['error']}")
                    else:
                        print(res)
            print()
    except KeyboardInterrupt:
        print("\n退出")


def start_legacy_cli():
    """启动原有 CLI 模式。"""
    print("启动 CLI 模式 (v4)...")
    from cli import main as cli_main
    cli_main()


def main():
    parser = argparse.ArgumentParser(
        description="Phone Automation System — Bootstrap Launcher",
    )
    parser.add_argument("--mode", choices=["marvis", "cli", "auto"], default="auto",
                        help="启动模式: marvis=AI调度, cli=原CLI, auto=自动检测")
    parser.add_argument("--status", "-s", action="store_true", help="显示环境状态")
    parser.add_argument("--task", "-t", help="直接执行任务（Marvis 模式）")
    parser.add_argument("--no-adb", action="store_true", help="不尝试 ADB 连接")
    args = parser.parse_args()

    env = detect_environment()

    if args.status:
        print_status(env)
        return

    # 模式选择
    mode = args.mode
    if mode == "auto":
        # 有 ADB 且是 Termux → 优先 Marvis
        if env["is_termux"] and (env["has_adb"] or env["has_shizuku"]):
            mode = "marvis"
        elif env["has_ollama"]:
            mode = "marvis"
        else:
            mode = "cli"

    if mode == "marvis":
        if args.task:
            from marvis_orchestrator.hub import MarvisHub
            hub = MarvisHub(ollama_url=env.get("ollama_url", "http://127.0.0.1:11434"))
            init_status = hub.init(connect_adb=not args.no_adb and env.get("has_adb", False))
            result = hub.dispatch(args.task)
            res = result.get("result", result)
            if isinstance(res, dict):
                summary = res.get("summary", res.get("observation", ""))
                print(summary or json.dumps(res, ensure_ascii=False, indent=2))
        else:
            start_marvis(env)
    else:
        start_legacy_cli()


if __name__ == "__main__":
    main(())
