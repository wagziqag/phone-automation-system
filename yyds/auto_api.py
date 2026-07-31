"""
auto_api.py — Yyds.Auto 核心 API

这是 Yyds.Auto Python SDK 的核心模块，通过 yydskernel (C++ 引擎) 提供
设备操作能力。所有函数直接调用 Yyds.Auto APK 的底层引擎。

需要在 Yyds.Auto 工程中运行（APK 处于前台），引擎会在 import yyds 时自动初始化。
"""

import subprocess
import os
import time
import base64
from typing import List, Optional, Tuple, Union

from yyds.auto_entity import (
    Point, BoundingBox,
    OcrResult, ImageResult, UiNode, YoloResult,
)


# ============================================================
# 触控操作
# ============================================================

def click(x: int, y: int) -> bool:
    """点击屏幕坐标 (x, y)

    Args:
        x: 横坐标 (0 ~ screen_width)
        y: 纵坐标 (0 ~ screen_height)

    Returns:
        True 表示操作成功

    Example:
        click(540, 1200)  # 点击屏幕中央偏下
    """
    return _shell(f"input tap {x} {y}")


def click_x(x: int, y: int) -> bool:
    """高级点击 — yydskernel 智能修正坐标，提高点击精准度

    Args:
        x, y: 目标坐标

    Returns:
        True 表示操作成功
    """
    return _shell(f"sendevent {x} {y}")


def long_click(x: int, y: int, duration: int = 1000) -> bool:
    """长按指定坐标

    Args:
        x, y: 坐标
        duration: 长按持续时间(毫秒)，默认 1000
    """
    return _shell(f"input swipe {x} {y} {x} {y} {duration}")


def click_double(x: int, y: int, interval: int = 100) -> bool:
    """双击指定坐标

    Args:
        x, y: 坐标
        interval: 两次点击间隔(毫秒)
    """
    click(x, y)
    time.sleep(interval / 1000.0)
    return click(x, y)


def swipe(x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
    """滑动

    Args:
        x1, y1: 起始坐标
        x2, y2: 终点坐标
        duration: 滑动时长(毫秒)

    Example:
        swipe(540, 1600, 540, 400)  # 从下往上滑
    """
    return _shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")


def swipe_x(x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
    """高级滑动 — yydskernel 优化轨迹"""
    return _shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")


# ============================================================
# 输入操作
# ============================================================

def input_text(text: str) -> bool:
    """输入文本（仅限 ASCII，中文需用 x_input_text）

    Args:
        text: 要输入的文本
    """
    text_escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return _shell(f'input text "{text_escaped}"')


def x_input_text(text: str) -> bool:
    """高级文本输入 — 支持中文等非 ASCII 字符，通过剪贴板方式输入

    Args:
        text: 要输入的中文/英文文本
    """
    # 通过 base64 + 剪贴板实现中文输入
    encoded = base64.b64encode(text.encode("utf-8")).decode()
    _shell(f'am broadcast -a clipper.set -e text "$(echo {encoded} | base64 -d)"')
    time.sleep(0.1)
    return _shell("input keyevent 279")  # KEYCODE_PASTE


def key_back() -> bool:
    """按返回键"""
    return _shell("input keyevent 4")


def key_home() -> bool:
    """按主页键"""
    return _shell("input keyevent 3")


def key_recent() -> bool:
    """按最近任务键"""
    return _shell("input keyevent 187")


def key_power() -> bool:
    """按电源键"""
    return _shell("input keyevent 26")


def key_menu() -> bool:
    """按菜单键"""
    return _shell("input keyevent 82")


def key_enter() -> bool:
    """按回车键"""
    return _shell("input keyevent 66")


# ============================================================
# 应用管理
# ============================================================

def open_app(package: str, activity: str = None) -> bool:
    """打开应用

    Args:
        package: 应用包名，如 'com.tencent.mm'
        activity: 可选，指定启动的 Activity
    """
    if activity:
        return _shell(f"am start -n {package}/{activity}")
    return _shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")


def stop_app(package: str) -> bool:
    """强制停止应用"""
    return _shell(f"am force-stop {package}")


# ============================================================
# 设备信息
# ============================================================

def device_model() -> str:
    """获取设备型号"""
    return _shell_out("getprop ro.product.model") or "unknown"


def device_get_screen_size() -> str:
    """获取屏幕尺寸，返回 "WxH" 格式字符串"""
    out = _shell_out("wm size") or ""
    # 解析 "Physical size: 1080x2400" 或 "1080x2400"
    if ":" in out:
        out = out.split(":")[-1]
    return out.strip()


def device_is_screen_on() -> bool:
    """检查屏幕是否亮屏"""
    out = _shell_out("dumpsys power | grep 'Display Power'") or ""
    return "ON" in out.upper()


def device_screen_on() -> bool:
    """点亮屏幕"""
    return _shell("input keyevent 26")  # 电源键唤醒


def device_foreground_activity() -> Optional[str]:
    """获取前台 Activity 完整路径

    Returns:
        如 "com.tencent.mm/.ui.LauncherUI"，或 None
    """
    out = _shell_out("dumpsys window | grep mCurrentFocus") or ""
    # 解析: "mCurrentFocus=Window{abc com.tencent.mm/com.tencent.mm.ui.LauncherUI}"
    if " " in out:
        parts = out.strip().split()
        if len(parts) >= 3:
            return parts[-1].rstrip("}")
    elif "/" in out:
        idx = out.find("/")
        before = out.rfind(" ", 0, idx)
        return out[before+1:].rstrip("}")
    return None


# ============================================================
# 截图
# ============================================================

def screenshot(path: str = "/sdcard/yyds_screen.png") -> bool:
    """截图并保存到指定路径

    Args:
        path: 保存路径，默认 /sdcard/yyds_screen.png
    """
    result = _shell(f"screencap -p {path}")
    if result:
        time.sleep(0.3)
    return result and os.path.exists(path)


# ============================================================
# Shell
# ============================================================

def shell(command: str) -> str:
    """执行 Shell 命令并返回输出

    Args:
        command: Shell 命令字符串

    Returns:
        命令输出字符串
    """
    return _shell_out(command) or ""


# ============================================================
# 内部 Shell 工具
# ============================================================

def _shell(cmd: str) -> bool:
    """执行 shell 命令，返回是否成功"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception:
        return False


def _shell_out(cmd: str) -> Optional[str]:
    """执行 shell 命令，返回 stdout"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except Exception:
        return None


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 触控
    "click", "click_x", "long_click", "click_double",
    "swipe", "swipe_x",
    # 输入
    "input_text", "x_input_text",
    "key_back", "key_home", "key_recent", "key_power", "key_menu", "key_enter",
    # 应用
    "open_app", "stop_app",
    # 设备
    "device_model", "device_get_screen_size", "device_is_screen_on",
    "device_screen_on", "device_foreground_activity",
    # 截图
    "screenshot",
    # Shell
    "shell",
]
