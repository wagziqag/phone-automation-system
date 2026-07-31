"""
yyds_ops.py — Yyds.Auto 快捷操作函数

直接调用，无需实例化 YydsBackend。适合在交互式环境或简单脚本中使用。

用法:
  from yyds_ops import tap, ocr_text, find_text, click_text, swipe_up

  tap(542, 948)                          # 点击
  lines = ocr_text()                     # 获取屏幕上所有文字
  pos = find_text("微信")                # 找"微信"的位置
  click_text("微信")                     # 找"微信"并点击
  swipe_up()                             # 向上滑动
"""

from modules.yyds_backend import get_yyds_backend, yyds_available

_yb = None

def _get() -> "YydsBackend":
    global _yb
    if _yb is None:
        _yb = get_yyds_backend()
    return _yb


# ═══ 触控快捷 ═══

def tap(x: int, y: int) -> bool:
    """点击坐标"""
    return _get().click(x, y)

def tap_smart(x: int, y: int) -> bool:
    """智能点击"""
    return _get().click_smart(x, y)

def long_tap(x: int, y: int, ms: int = 1000) -> bool:
    """长按"""
    return _get().long_press(x, y, ms)

def swipe(x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
    """滑动"""
    return _get().swipe(x1, y1, x2, y2, duration)

def swipe_up(from_y: int = 1600, to_y: int = 400, x: int = 540) -> bool:
    """向上滑（默认屏幕中央）"""
    return _get().swipe(x, from_y, x, to_y)

def swipe_down(from_y: int = 400, to_y: int = 1600, x: int = 540) -> bool:
    """向下滑"""
    return _get().swipe(x, from_y, x, to_y)

def swipe_left(from_x: int = 900, to_x: int = 100, y: int = 1200) -> bool:
    """向左滑"""
    return _get().swipe(from_x, y, to_x, y)

def swipe_right(from_x: int = 100, to_x: int = 900, y: int = 1200) -> bool:
    """向右滑"""
    return _get().swipe(from_x, y, to_x, y)

def back() -> bool:
    """按返回键"""
    return _get().press_back()

def home() -> bool:
    """按主页键"""
    return _get().press_home()


# ═══ 输入快捷 ═══

def type_text(text: str) -> bool:
    """输入文本"""
    return _get().input_text(text)


# ═══ 应用快捷 ═══

def open(package: str) -> bool:
    """打开应用"""
    return _get().open_app(package)

def stop(package: str) -> bool:
    """停止应用"""
    return _get().stop_app(package)

def current_app() -> str:
    """获取当前前台应用"""
    return _get().get_foreground_activity() or ""


# ═══ OCR 快捷 ═══

def ocr_text(save_path: str = None) -> list:
    """获取屏幕 OCR 文本列表 [{"text":..., "cx":..., "cy":..., "prob":...}, ...]"""
    return _get().ocr(save_path)

def ocr_lines() -> list:
    """获取屏幕 OCR 纯文本行列表"""
    return [r["text"] for r in _get().ocr()]

def find_text(keyword: str) -> dict:
    """查找包含关键词的第一个文本位置，返回 {text, cx, cy, prob, ...} 或 None"""
    return _get().find_text(keyword)

def find_text_all(keyword: str) -> list:
    """查找所有包含关键词的文本位置"""
    return _get().find_text_all(keyword)

def click_text(keyword: str) -> bool:
    """查找文本并点击"""
    return _get().find_and_click_text(keyword)

def wait_text(keyword: str, timeout: float = 10.0) -> dict:
    """等待文本出现"""
    return _get().wait_for_text(keyword, timeout)

def wait_click(keyword: str, timeout: float = 10.0) -> bool:
    """等待文本出现并点击"""
    return _get().wait_and_click(keyword, timeout)


# ═══ 图像模板快捷 ═══

def find_img(template: str, threshold: float = 0.8) -> dict:
    """屏幕图像匹配"""
    return _get().find_image(template, threshold)

def click_img(template: str, threshold: float = 0.8) -> bool:
    """匹配图像并点击"""
    return _get().click_image(template, threshold)


# ═══ UI 匹配快捷 ═══

def find_ui(**kwargs) -> dict:
    """匹配 UI 元素"""
    return _get().ui_match(**kwargs)

def click_ui(**kwargs) -> bool:
    """匹配 UI 元素并点击"""
    return _get().ui_click(**kwargs)


# ═══ 截图快捷 ═══

def screenshot(path: str = "/sdcard/screen.png") -> bool:
    """截图保存"""
    return _get().screenshot(path)


# ═══ 状态 ═══

def status() -> dict:
    """获取 yyds 状态报告"""
    return _get().status_report()

def capabilities() -> dict:
    """获取能力列表"""
    return _get().get_capabilities()

def is_available() -> bool:
    """检查 yyds 是否可用"""
    return yyds_available()
