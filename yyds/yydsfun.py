"""
yydsfun.py — Yyds.Auto 预设脚本库

常用操作的预设函数，基于 auto_api 和 auto_plus 封装。
适合导入手动编写自动化脚本时直接调用。
"""

import time
from yyds.auto_api import *
from yyds.auto_api_aux import *
from yyds.auto_plus import DeviceScreen
from yyds.util import log_d, log_e, sleep


# 全局屏幕实例
screen = DeviceScreen()


# ── 常用应用操作 ──

def open_wechat() -> bool:
    """打开微信"""
    return open_app("com.tencent.mm")


def open_qq() -> bool:
    """打开 QQ"""
    return open_app("com.tencent.mobileqq")


def open_alipay() -> bool:
    """打开支付宝"""
    return open_app("com.eg.android.AlipayGphone")


def open_settings() -> bool:
    """打开系统设置"""
    return open_app("com.android.settings")


def is_app_open(package: str) -> bool:
    """检查指定应用是否在前台"""
    activity = device_foreground_activity()
    return activity is not None and package in activity


# ── 快捷操作 ──

def click_center() -> bool:
    """点击屏幕中心"""
    return click(screen.width // 2, screen.height // 2)


def click_bottom_center() -> bool:
    """点击屏幕底部中央"""
    return click(screen.width // 2, int(screen.height * 0.9))


def click_top_right() -> bool:
    """点击右上角"""
    return click(int(screen.width * 0.95), int(screen.height * 0.05))


def dismiss_dialog(keywords: list = None) -> bool:
    """尝试关闭弹窗（点击常见关闭按钮文本）

    Args:
        keywords: 要匹配的文本列表，默认 ["确定", "取消", "关闭", "我知道了", "同意"]
    """
    if keywords is None:
        keywords = ["确定", "取消", "关闭", "我知道了", "同意", "不允许", "暂不", "跳过"]
    for kw in keywords:
        if screen.tap_text(kw):
            return True
    return False


def restart_app(package: str, wait: float = 2.0) -> bool:
    """重启应用"""
    stop_app(package)
    time.sleep(wait)
    return open_app(package)


# ── 文本读取 ──

def read_screen_text(keywords: list = None) -> dict:
    """读取屏幕文字，按关键词过滤

    Args:
        keywords: 要搜索的关键词列表，None 返回所有

    Returns:
        {keyword: OcrResult} 字典
    """
    if keywords is None:
        return {r.text: r for r in screen.ocr()}

    results = {}
    for r in screen.ocr():
        for kw in keywords:
            if kw in (r.text or ""):
                results[kw] = r
    return results


# ── 流程辅助 ──

def flow(steps: list) -> bool:
    """执行预定义的操作流程

    每一步是一个元组: (操作名, 参数)
    支持的操作:
      ("click", x, y)
      ("tap_text", keyword)
      ("swipe", x1, y1, x2, y2, duration)
      ("text", text)
      ("wait", seconds)
      ("wait_text", keyword)
      ("home",)
      ("back",)
      ("open_app", package)

    Example:
        flow([
            ("open_app", "com.tencent.mm"),
            ("wait_text", "发现"),
            ("click", 540, 2000),
        ])
    """
    for step in steps:
        action = step[0]
        try:
            if action == "click":
                click(step[1], step[2])
            elif action == "tap_text":
                screen.tap_text(step[1])
            elif action == "swipe":
                duration = step[5] if len(step) > 5 else 300
                swipe(step[1], step[2], step[3], step[4], duration)
            elif action == "text":
                x_input_text(step[1])
            elif action == "wait":
                time.sleep(step[1])
            elif action == "wait_text":
                if not screen.wait_for(step[1]):
                    log_e(f"flow: wait_text '{step[1]}' timed out")
                    return False
            elif action == "home":
                key_home()
            elif action == "back":
                key_back()
            elif action == "open_app":
                open_app(step[1])
            else:
                log_e(f"flow: unknown action '{action}'")
                return False
        except Exception as e:
            log_e(f"flow: step {step} failed: {e}")
            return False
    return True


__all__ = [
    "screen",
    "open_wechat", "open_qq", "open_alipay", "open_settings",
    "is_app_open",
    "click_center", "click_bottom_center", "click_top_right",
    "dismiss_dialog", "restart_app",
    "read_screen_text",
    "flow",
]
