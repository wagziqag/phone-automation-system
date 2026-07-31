"""
yyds_backend.py — Yyds.Auto 后端适配器

将 Yyds.Auto 的 Python API 封装为 phone-automation-system 的标准后端接口，
与 rish/ADB/shell 后端并列，支持丰富操作：OCR、YOLO、UI匹配、图像模板匹配等。

Yyds.Auto 依赖:
  - Yyds.Auto APK (com.yyds.msu) 需前台运行
  - Python 工程中需有 yyds/ 目录（auto_api, auto_api_aux, auto_func, auto_plus 等）
  - 底层依赖 yydskernel (C++ 引擎)

使用方式:
  from modules.yyds_backend import YydsBackend
  yb = YydsBackend()
  result = yb.click(542, 948)
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("yyds_backend")

# ── 动态导入 yyds ──
YYDS_AVAILABLE = False
YYDS_MODULES = {}

# 尝试查找 yyds 目录
_YYDS_PATHS = [
    Path(__file__).resolve().parent.parent / "yyds",  # 项目根/yyds
    Path("/data/data/com.termux/files/home/phone-automation-system/yyds"),
    Path("/sdcard/Yyds.Py/phone_automation"),
]

for _p in _YYDS_PATHS:
    if _p.exists() and (_p / "auto_api.py").exists():
        sys.path.insert(0, str(_p.parent))
        try:
            from yyds.auto_api import *
            from yyds.auto_api_aux import *  # screen_find_image_x, screen_ocr_x, click_double 等
            from yyds.auto_func import *      # WrapRecord, try_run
            from yyds.auto_plus import *      # DeviceScreen
            from yyds.auto_entity import *    # Point, Color
            from yyds.util import log_d, log_e, format_time
            YYDS_AVAILABLE = True
            YYDS_MODULES["path"] = str(_p)
            logger.info(f"yyds loaded from {_p}")
            break
        except ImportError as e:
            logger.debug(f"yyds import failed from {_p}: {e}")
            continue

# yyds 核心 API 列表（用于存在性检测和功能注册）
YYDS_CORE_APIS = {
    # 触控
    "click":         "点击坐标",
    "click_x":       "高级点击（智能修正）",
    "click_double":  "双击",
    "long_click":    "长按",
    "swipe":         "滑动",
    "swipe_x":       "高级滑动",

    # 输入
    "input_text":    "输入文本",
    "x_input_text":  "高级文本输入",
    "key_back":      "返回键",
    "key_home":      "主页键",

    # 截图
    "screenshot":    "截图（保存到文件）",

    # 应用管理
    "open_app":      "打开应用",
    "stop_app":      "停止应用",
    "device_foreground_activity": "获取前台 Activity",

    # 设备信息
    "device_model":           "设备型号",
    "device_get_screen_size": "屏幕尺寸",
    "device_is_screen_on":    "屏幕是否亮屏",

    # Shell
    "shell":         "执行 Shell 命令",

    # OCR（yydskernel 引擎）
    "screen_ocr_x":  "屏幕 OCR（返回结构化结果）",

    # 图像匹配
    "screen_find_image_x":    "屏幕图像模板匹配",
    "screen_find_image_all_x": "查找所有匹配",

    # UI 匹配
    "ui_match":     "UI 元素匹配",
    "ui_exist":     "UI 元素存在性检查",

    # YOLO 目标检测（若 yyds 版本支持）
    "screen_yolo_find_x":     "YOLO 目标查找",
    "screen_yolo_find_all_x": "YOLO 查找所有目标",
}


class YydsBackend:
    """Yyds.Auto 后端适配器

    提供与 ADB/rish 后端一致的接口，并扩展 OCR/UI匹配/图像查找等高级能力。
    """

    def __init__(self):
        self.available = YYDS_AVAILABLE
        self._screen_w = 1080
        self._screen_h = 2400
        self._capabilities: Dict[str, bool] = {}
        if self.available:
            self._detect_screen()
            self._scan_apis()

    # ═══ 基础信息 ═══

    @property
    def name(self) -> str:
        return "yyds"

    def _detect_screen(self):
        try:
            size = device_get_screen_size()
            w, h = size.split("x") if isinstance(size, str) else (size.width, size.height)
            self._screen_w = int(w)
            self._screen_h = int(h)
        except Exception:
            pass

    def get_screen_size(self) -> Tuple[int, int]:
        return self._screen_w, self._screen_h

    def get_device_model(self) -> str:
        if self.available:
            try:
                return device_model()
            except Exception:
                pass
        return "unknown"

    # ═══ 能力扫描 ═══

    def _scan_apis(self) -> Dict[str, bool]:
        """扫描当前 yyds 环境实际可用的 API"""
        caps = {}
        for api_name in YYDS_CORE_APIS:
            try:
                func = globals().get(api_name)
                caps[api_name] = func is not None and callable(func)
            except Exception:
                caps[api_name] = False
        self._capabilities = caps
        return caps

    def get_capabilities(self) -> Dict[str, bool]:
        """返回当前可用的 yyds 能力表"""
        if not self._capabilities:
            self._scan_apis()
        return dict(self._capabilities)

    def list_available_apis(self) -> List[str]:
        return [k for k, v in self.get_capabilities().items() if v]

    # ═══ 触控操作 ═══

    def click(self, x: int, y: int) -> bool:
        """点击指定坐标"""
        if not self.available:
            return False
        try:
            click(x, y)
            return True
        except Exception as e:
            logger.error(f"yyds.click({x},{y}): {e}")
            return False

    def click_smart(self, x: int, y: int) -> bool:
        """高级点击（yydskernel 智能修正）"""
        if not self.available:
            return False
        try:
            click_x(x, y)
            return True
        except Exception:
            return self.click(x, y)  # 降级

    def double_click(self, x: int, y: int) -> bool:
        if not self.available:
            return False
        try:
            click_double(x, y)
            return True
        except Exception:
            return False

    def long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        if not self.available:
            return False
        try:
            long_click(x, y, duration)
            return True
        except Exception:
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        if not self.available:
            return False
        try:
            swipe(x1, y1, x2, y2, duration)
            return True
        except Exception:
            return False

    def swipe_smart(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        if not self.available:
            return False
        try:
            swipe_x(x1, y1, x2, y2, duration)
            return True
        except Exception:
            return self.swipe(x1, y1, x2, y2, duration)

    # ═══ 输入操作 ═══

    def input_text(self, text: str) -> bool:
        if not self.available:
            return False
        try:
            x_input_text(text) if self._capabilities.get("x_input_text") else input_text(text)
            return True
        except Exception as e:
            logger.error(f"yyds.input_text: {e}")
            return False

    def press_back(self) -> bool:
        if not self.available:
            return False
        try:
            key_back()
            return True
        except Exception:
            return False

    def press_home(self) -> bool:
        if not self.available:
            return False
        try:
            key_home()
            return True
        except Exception:
            return False

    # ═══ 应用管理 ═══

    def open_app(self, package: str) -> bool:
        if not self.available:
            return False
        try:
            open_app(package)
            return True
        except Exception:
            return False

    def stop_app(self, package: str) -> bool:
        if not self.available:
            return False
        try:
            stop_app(package)
            return True
        except Exception:
            return False

    def get_foreground_activity(self) -> Optional[str]:
        if not self.available:
            return None
        try:
            result = device_foreground_activity()
            if hasattr(result, 'activity'):
                return result.activity
            return str(result)
        except Exception:
            return None

    # ═══ 截图 ═══

    def screenshot(self, path: str) -> bool:
        """截图并保存到指定路径"""
        if not self.available:
            return False
        try:
            screenshot(path)
            return os.path.exists(path)
        except Exception as e:
            logger.error(f"yyds.screenshot: {e}")
            return False

    # ═══ Shell ═══

    def shell(self, cmd: str) -> Tuple[str, int]:
        """执行 Shell 命令，返回 (output, rc)"""
        if not self.available:
            return "", -1
        try:
            result = shell(cmd)
            return str(result), 0
        except Exception as e:
            return str(e), -1

    # ═══ OCR ═══

    def ocr(self, save_path: str = None) -> List[Dict]:
        """屏幕 OCR，返回结构化结果

        返回: [{"text": str, "cx": int, "cy": int, "prob": float,
                "x1": int, "y1": int, "x3": int, "y3": int}, ...]
        """
        if not self.available or not self._capabilities.get("screen_ocr_x"):
            return []
        try:
            kwargs = {}
            if save_path:
                kwargs["save_path"] = save_path
            results = screen_ocr_x(**kwargs)
            return [
                {
                    "text": r.text,
                    "cx": r.cx, "cy": r.cy,
                    "x1": r.x1, "y1": r.y1,
                    "x3": r.x3, "y3": r.y3,
                    "prob": getattr(r, 'prob', 1.0),
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"yyds.ocr: {e}")
            return []

    def find_text(self, keyword: str) -> Optional[Dict]:
        """查找包含指定关键词的文本位置"""
        results = self.ocr()
        for r in results:
            if keyword in r.get("text", ""):
                return r
        return None

    def find_text_all(self, keyword: str) -> List[Dict]:
        """查找所有包含指定关键词的文本"""
        results = self.ocr()
        return [r for r in results if keyword in r.get("text", "")]

    # ═══ 图像模板匹配 ═══

    def find_image(self, template_path: str, threshold: float = 0.8) -> Optional[Dict]:
        """屏幕图像模板匹配（返回最佳匹配）

        返回: {"name": str, "cx": int, "cy": int, "prob": float,
                "x": int, "y": int, "w": int, "h": int} 或 None
        """
        if not self.available or not self._capabilities.get("screen_find_image_x"):
            return None
        try:
            results = screen_find_image_x(template_path, threshold)
            if results:
                r = results[0]
                return {
                    "name": getattr(r, 'name', ''),
                    "cx": r.cx, "cy": r.cy,
                    "x": r.x, "y": r.y,
                    "w": r.width, "h": r.height,
                    "prob": r.prob,
                }
        except Exception as e:
            logger.error(f"yyds.find_image: {e}")
        return None

    def find_image_all(self, template_path: str, threshold: float = 0.8) -> List[Dict]:
        """查找所有匹配的模板图像位置"""
        if not self.available or not self._capabilities.get("screen_find_image_all_x"):
            return []
        try:
            results = screen_find_image_all_x(template_path, threshold)
            return [
                {
                    "name": r.name, "cx": r.cx, "cy": r.cy,
                    "x": r.x, "y": r.y, "w": r.width, "h": r.height,
                    "prob": r.prob,
                }
                for r in results
            ]
        except Exception:
            return []

    def click_image(self, template_path: str, threshold: float = 0.8) -> bool:
        """找到模板图像并点击其中心"""
        match = self.find_image(template_path, threshold)
        if match and match["prob"] >= threshold:
            return self.click(match["cx"], match["cy"])
        return False

    # ═══ UI 匹配 ═══

    def ui_match(self, **kwargs) -> Optional[Any]:
        """UI 元素匹配

        参数:
          class_name: str - 类名
          text: str - 文本
          desc: str - 描述
          id: str - ID
        返回匹配到的第一个 UI 节点 或 None
        """
        if not self.available or not self._capabilities.get("ui_match"):
            return None
        try:
            return ui_match(**kwargs)
        except Exception as e:
            logger.error(f"yyds.ui_match: {e}")
            return None

    def ui_click(self, **kwargs) -> bool:
        """匹配 UI 元素并点击"""
        node = self.ui_match(**kwargs)
        if node and hasattr(node, 'center_point'):
            cx, cy = node.center_point
            return self.click(cx, cy)
        return False

    # ═══ YOLO 目标检测 ═══

    def yolo_find(self, label: str, threshold: float = 0.5) -> Optional[Dict]:
        """YOLO 查找指定标签的目标"""
        if not self.available or not self._capabilities.get("screen_yolo_find_x"):
            return None
        try:
            results = screen_yolo_find_x(label, threshold)
            if results:
                r = results[0]
                return {
                    "label": r.label, "prob": r.prob,
                    "cx": r.cx, "cy": r.cy,
                    "x": r.x, "y": r.y,
                    "w": r.w, "h": r.h,
                }
        except Exception:
            return None

    def yolo_find_all(self, label: str = None, threshold: float = 0.5) -> List[Dict]:
        """YOLO 查找所有目标"""
        if not self.available or not self._capabilities.get("screen_yolo_find_all_x"):
            return []
        try:
            results = screen_yolo_find_all_x(label, threshold) if label else screen_yolo_find_all_x(threshold=threshold)
            return [
                {
                    "label": r.label, "prob": r.prob,
                    "cx": r.cx, "cy": r.cy,
                    "x": r.x, "y": r.y,
                    "w": r.w, "h": r.h,
                }
                for r in results
            ]
        except Exception:
            return []

    # ═══ 复合操作 ═══

    def find_and_click_text(self, keyword: str) -> bool:
        """OCR 查找文本并点击（最常用的复合操作）"""
        match = self.find_text(keyword)
        if match:
            return self.click(match["cx"], match["cy"])
        return False

    def wait_for_text(self, keyword: str, timeout: float = 10.0, interval: float = 0.5) -> Optional[Dict]:
        """等待某段文字出现在屏幕上，返回其位置"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            match = self.find_text(keyword)
            if match:
                return match
            time.sleep(interval)
        return None

    def wait_and_click(self, keyword: str, timeout: float = 10.0) -> bool:
        """等待文字出现并点击"""
        match = self.wait_for_text(keyword, timeout)
        if match:
            return self.click(match["cx"], match["cy"])
        return False

    # ═══ 状态报告 ═══

    def status_report(self) -> Dict:
        """生成后端状态报告"""
        return {
            "backend": "yyds",
            "available": self.available,
            "yyds_path": YYDS_MODULES.get("path", "not found"),
            "screen": f"{self._screen_w}x{self._screen_h}",
            "model": self.get_device_model() if self.available else "unknown",
            "apis_available": self.list_available_apis(),
            "apis_total": len(YYDS_CORE_APIS),
            "rich_features": {
                "ocr": self._capabilities.get("screen_ocr_x", False),
                "image_match": self._capabilities.get("screen_find_image_x", False),
                "yolo": self._capabilities.get("screen_yolo_find_x", False),
                "ui_match": self._capabilities.get("ui_match", False),
            }
        }


# ═══ 便捷函数 ═══

# 全局单例
_yyds_instance: Optional[YydsBackend] = None


def get_yyds_backend() -> YydsBackend:
    """获取 YydsBackend 单例"""
    global _yyds_instance
    if _yyds_instance is None:
        _yyds_instance = YydsBackend()
    return _yyds_instance


def yyds_available() -> bool:
    """检查 yyds 是否可用"""
    return YYDS_AVAILABLE


def yyds_capabilities() -> Dict[str, bool]:
    """获取 yyds 能力表（不创建完整后端实例）"""
    if not YYDS_AVAILABLE:
        return {k: False for k in YYDS_CORE_APIS}
    return get_yyds_backend().get_capabilities()
