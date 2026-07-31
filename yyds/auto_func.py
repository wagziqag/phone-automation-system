"""
auto_func.py — Yyds.Auto 工具函数与装饰器

提供录制、重试、计时等辅助功能。
"""

import time
import traceback
import functools
from typing import Any, Callable, Optional, Type, Tuple

from yyds.util import log_d, log_e


class WrapRecord:
    """操作录制器 — 记录每一步操作，便于回放和调试

    Usage:
        record = WrapRecord()
        record.click(540, 1200)
        record.swipe(540, 1600, 540, 400)
        print(record.history)  # 查看操作历史
        record.replay()        # 回放
    """
    def __init__(self, name: str = "record"):
        self.name = name
        self.history: list = []
        self._start_time = time.time()

    def _log(self, action: str, args: tuple, kwargs: dict, result: Any):
        entry = {
            "timestamp": time.time() - self._start_time,
            "action": action,
            "args": args,
            "kwargs": kwargs,
            "result": str(result)[:200]
        }
        self.history.append(entry)

    def click(self, x: int, y: int) -> "WrapRecord":
        from yyds.auto_api import click
        result = click(x, y)
        self._log("click", (x, y), {}, result)
        return self

    def click_x(self, x: int, y: int) -> "WrapRecord":
        from yyds.auto_api import click_x
        result = click_x(x, y)
        self._log("click_x", (x, y), {}, result)
        return self

    def long_click(self, x: int, y: int, duration: int = 1000) -> "WrapRecord":
        from yyds.auto_api import long_click
        result = long_click(x, y, duration)
        self._log("long_click", (x, y, duration), {}, result)
        return self

    def swipe(self, x1, y1, x2, y2, duration=300) -> "WrapRecord":
        from yyds.auto_api import swipe
        result = swipe(x1, y1, x2, y2, duration)
        self._log("swipe", (x1, y1, x2, y2), {"duration": duration}, result)
        return self

    def swipe_x(self, x1, y1, x2, y2, duration=300) -> "WrapRecord":
        from yyds.auto_api import swipe_x
        result = swipe_x(x1, y1, x2, y2, duration)
        self._log("swipe_x", (x1, y1, x2, y2), {"duration": duration}, result)
        return self

    def text(self, text: str) -> "WrapRecord":
        from yyds.auto_api import x_input_text
        result = x_input_text(text)
        self._log("text", (text,), {}, result)
        return self

    def back(self) -> "WrapRecord":
        from yyds.auto_api import key_back
        result = key_back()
        self._log("back", (), {}, result)
        return self

    def home(self) -> "WrapRecord":
        from yyds.auto_api import key_home
        result = key_home()
        self._log("home", (), {}, result)
        return self

    def sleep(self, seconds: float) -> "WrapRecord":
        time.sleep(seconds)
        self._log("sleep", (seconds,), {}, True)
        return self

    def ocr(self) -> "WrapRecord":
        from yyds.auto_api_aux import screen_ocr_x
        result = screen_ocr_x()
        self._log("ocr", (), {}, f"{len(result)} results")
        return self

    def wait_text(self, keyword: str, timeout: float = 10.0) -> "WrapRecord":
        start = time.time()
        from yyds.auto_api_aux import screen_ocr_x
        while time.time() - start < timeout:
            results = screen_ocr_x()
            for r in results:
                if keyword in (r.text or ""):
                    self.click(r.cx, r.cy)
                    self._log("wait_text", (keyword,), {"timeout": timeout}, f"found at ({r.cx},{r.cy})")
                    return self
            time.sleep(0.5)
        self._log("wait_text", (keyword,), {"timeout": timeout}, "not found")
        return self

    def replay(self, loop: int = 1) -> None:
        """回放录制的操作"""
        from yyds.auto_api import click, click_x, swipe, swipe_x, long_click
        from yyds.auto_api import key_back, key_home, x_input_text

        for _ in range(loop):
            for entry in self.history:
                action = entry["action"]
                args = entry["args"]
                log_d(f"Replay: {action}{args}")
                if action == "click":
                    click(*args)
                elif action == "click_x":
                    click_x(*args)
                elif action == "swipe":
                    swipe(*args)
                elif action == "back":
                    key_back()
                elif action == "home":
                    key_home()
                elif action == "text":
                    x_input_text(args[0])
                elif action == "sleep":
                    time.sleep(args[0])
                # ocr/wait_text 在回放时跳过

    def summary(self) -> str:
        """生成操作摘要"""
        lines = [f"=== WrapRecord '{self.name}' ({len(self.history)} steps) ==="]
        for i, entry in enumerate(self.history):
            lines.append(
                f"  {i+1}. [{entry['timestamp']:.1f}s] "
                f"{entry['action']}{entry['args']} -> {entry['result']}"
            )
        return "\n".join(lines)


def try_run(
    func: Callable,
    *args,
    max_retries: int = 3,
    delay: float = 1.0,
    catch: Tuple[Type[Exception], ...] = (Exception,),
    **kwargs
) -> Tuple[bool, Any]:
    """带重试的执行函数

    Args:
        func: 要执行的函数
        *args: 位置参数
        max_retries: 最大重试次数
        delay: 每次重试间隔(秒)
        catch: 捕获的异常类型
        **kwargs: 关键字参数

    Returns:
        (success, result) — success=True 表示成功，result 为函数返回值

    Example:
        ok, result = try_run(click, 540, 1200, max_retries=3)
        if not ok:
            log_e("Click failed after 3 retries")
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            return True, result
        except catch as e:
            last_error = e
            log_e(f"try_run attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
    return False, last_error


def measure_time(func: Callable) -> Callable:
    """装饰器：测量函数执行时间

    Usage:
        @measure_time
        def my_func():
            time.sleep(1)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        log_d(f"[{func.__name__}] {elapsed*1000:.1f}ms")
        return result
    return wrapper


__all__ = ["WrapRecord", "try_run", "measure_time"]
