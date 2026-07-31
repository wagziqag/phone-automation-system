"""
yyds — Yyds.Auto Python SDK 包装层

在 Yyds.Auto 工程中运行时，import yyds 会自动初始化底层 yydskernel (C++) 引擎。
所有 auto_api 中的函数可直接调用。

Usage:
    from yyds import *

    # 基础操作
    click(540, 1200)
    swipe(540, 1600, 540, 400)

    # 高级操作
    from yyds.auto_api_aux import screen_ocr_x, screen_find_image_x
    results = screen_ocr_x()

    # 使用 DeviceScreen
    from yyds.auto_plus import DeviceScreen
    screen = DeviceScreen()
    screen.tap_text("微信")
"""

# 从 auto_api 导入所有基础 API（使 from yyds import * 可用）
from yyds.auto_api import *
from yyds.auto_api_aux import *
from yyds.auto_entity import *
from yyds.auto_func import *
from yyds.auto_plus import DeviceScreen
from yyds.util import *
from yyds.yydsfun import *

__version__ = "1.0.0"
__all__ = (
    auto_api.__all__ +
    auto_api_aux.__all__ +
    auto_entity.__all__ +
    auto_func.__all__ +
    util.__all__ +
    yydsfun.__all__ +
    ["DeviceScreen"]
)
