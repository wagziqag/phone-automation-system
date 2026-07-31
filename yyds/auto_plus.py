"""
auto_plus.py — Yyds.Auto 增强层 (DeviceScreen 高级屏幕操作)
"""

import time
import os
from typing import List, Optional, Dict, Tuple
from yyds.auto_api import *
from yyds.auto_api_aux import *
from yyds.auto_entity import OcrResult, Point, BoundingBox
from yyds.util import log_d


class DeviceScreen:
    """设备屏幕高级操作类

    封装 OCR + 触控的常用组合，提供面向意图的操作接口。

    Usage:
        screen = DeviceScreen()
        screen.tap_text("微信")
        screen.scroll_down()
        screen.wait_for("确认")
    """

    def __init__(self):
        size_str = device_get_screen_size()
        try:
            w, h = size_str.split("x")
            self.width = int(w)
            self.height = int(h)
        except Exception:
            self.width = 1080
            self.height = 2400
        self._wait_interval = 0.5

    # ── 信息 ──

    def ocr(self, save_path: str = None) -> List[OcrResult]:
        """获取屏幕 OCR 结果"""
        return screen_ocr_x(save_path=save_path)

    def text_lines(self) -> List[str]:
        """获取屏幕所有文字行"""
        return [r.text for r in self.ocr()]

    def find_text(self, keyword: str) -> Optional[OcrResult]:
        """查找包含关键词的第一个 OCR 结果"""
        for r in self.ocr():
            if keyword in (r.text or ""):
                return r
        return None

    def find_all_text(self, keyword: str) -> List[OcrResult]:
        """查找所有包含关键词的 OCR 结果"""
        return [r for r in self.ocr() if keyword in (r.text or "")]

    # ── 触控 ──

    def tap(self, x: int, y: int) -> bool:
        return click(x, y)

    def tap_smart(self, x: int, y: int) -> bool:
        return click_x(x, y)

    def tap_text(self, keyword: str) -> bool:
        """查找文本并点击其中心"""
        match = self.find_text(keyword)
        if match:
            return click(match.cx, match.cy)
        log_d(f"tap_text: '{keyword}' not found on screen")
        return False

    def tap_image(self, template: str, threshold: float = 0.8) -> bool:
        """查找模板图像并点击"""
        results = screen_find_image_x(template, threshold)
        if results and results[0].prob >= threshold:
            return click(results[0].cx, results[0].cy)
        return False

    def double_tap(self, x: int, y: int) -> bool:
        return click_double(x, y)

    def long_tap(self, x: int, y: int, duration: int = 1000) -> bool:
        return long_click(x, y, duration)

    # ── 滑动 ──

    def scroll_up(self, distance: float = 0.5) -> bool:
        """向上滚动"""
        cx = self.width // 2
        y1 = int(self.height * 0.65)
        y2 = int(self.height * (0.65 - distance))
        return swipe(cx, y1, cx, max(y2, 0))

    def scroll_down(self, distance: float = 0.5) -> bool:
        """向下滚动"""
        cx = self.width // 2
        y1 = int(self.height * 0.35)
        y2 = int(self.height * (0.35 + distance))
        return swipe(cx, y1, cx, min(y2, self.height))

    def scroll_left(self) -> bool:
        """向左滑动"""
        y = self.height // 2
        return swipe(int(self.width * 0.8), y, int(self.width * 0.2), y)

    def scroll_right(self) -> bool:
        """向右滑动"""
        y = self.height // 2
        return swipe(int(self.width * 0.2), y, int(self.width * 0.8), y)

    # ── 等待 ──

    def wait_for(self, keyword: str, timeout: float = 10.0) -> Optional[OcrResult]:
        """等待屏幕上出现指定文本"""
        start = time.time()
        while time.time() - start < timeout:
            match = self.find_text(keyword)
            if match:
                return match
            time.sleep(self._wait_interval)
        return None

    def wait_and_tap(self, keyword: str, timeout: float = 10.0) -> bool:
        """等待文本出现并点击"""
        match = self.wait_for(keyword, timeout)
        if match:
            return click(match.cx, match.cy)
        return False

    def wait_not(self, keyword: str, timeout: float = 10.0) -> bool:
        """等待文本消失"""
        start = time.time()
        while time.time() - start < timeout:
            if self.find_text(keyword) is None:
                return True
            time.sleep(self._wait_interval)
        return False

    # ── 输入 ──

    def type(self, text: str) -> bool:
        return x_input_text(text)

    def clear_and_type(self, text: str) -> bool:
        """选中全部并替换输入"""
        long_click(self.width // 2, self.height // 2)  # 长按触发全选
        time.sleep(0.2)
        return x_input_text(text)

    # ── 导航 ──
    go_back = key_back
    go_home = key_home

    # ── 截图 ──

    def capture(self, path: str = "/sdcard/screen.png") -> bool:
        return screenshot(path)

    # ── 复合 ──

    def scroll_to_find(self, keyword: str, max_scrolls: int = 10) -> Optional[OcrResult]:
        """滚动查找文本"""
        for _ in range(max_scrolls):
            match = self.find_text(keyword)
            if match:
                return match
            self.scroll_up()
            time.sleep(0.5)
        return None

    def scroll_to_find_and_tap(self, keyword: str, max_scrolls: int = 10) -> bool:
        """滚动查找文本并点击"""
        match = self.scroll_to_find(keyword, max_scrolls)
        if match:
            return click(match.cx, match.cy)
        return False

    def swipe_action(self, direction: str) -> bool:
        """方向滑动: up/down/left/right"""
        return {
            "up": self.scroll_up,
            "down": self.scroll_down,
            "left": self.scroll_left,
            "right": self.scroll_right,
        }.get(direction, lambda: False)()
