"""
util.py — Yyds.Auto 日志与工具函数
"""

import time
import os
import sys
from datetime import datetime

# 日志级别
LOG_LEVEL_DEBUG = 0
LOG_LEVEL_INFO = 1
LOG_LEVEL_WARN = 2
LOG_LEVEL_ERROR = 3

_current_log_level = LOG_LEVEL_DEBUG

# 日志文件路径
_LOG_FILE = "/sdcard/yyds_log.txt"


def set_log_level(level: int):
    """设置日志级别"""
    global _current_log_level
    _current_log_level = level


def set_log_file(path: str):
    """设置日志文件路径"""
    global _LOG_FILE
    _LOG_FILE = path


def format_time(timestamp: float = None) -> str:
    """格式化时间戳"""
    if timestamp is None:
        timestamp = time.time()
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]


def _log(level: int, tag: str, *args):
    """内部日志函数"""
    if level < _current_log_level:
        return

    msg = " ".join(str(a) for a in args)
    line = f"[{format_time()}] [{tag}] {msg}"

    # 输出到 stdout
    print(line, file=sys.stdout, flush=True)

    # 追加到日志文件
    try:
        os.makedirs(os.path.dirname(_LOG_FILE) or "/sdcard", exist_ok=True)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def log_d(*args):
    """调试日志"""
    _log(LOG_LEVEL_DEBUG, "D", *args)


def log_i(*args):
    """信息日志"""
    _log(LOG_LEVEL_INFO, "I", *args)


def log_w(*args):
    """警告日志"""
    _log(LOG_LEVEL_WARN, "W", *args)


def log_e(*args):
    """错误日志"""
    _log(LOG_LEVEL_ERROR, "E", *args)


def sleep(seconds: float):
    """带日志的延迟"""
    log_d(f"sleep({seconds}s)")
    time.sleep(seconds)


def wait_until(condition, timeout: float = 10.0, interval: float = 0.5) -> bool:
    """等待条件成立

    Args:
        condition: 返回 bool 的可调用对象
        timeout: 超时(秒)
        interval: 检查间隔(秒)
    """
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False


__all__ = [
    "log_d", "log_i", "log_w", "log_e",
    "format_time", "set_log_level", "set_log_file",
    "sleep", "wait_until",
]
