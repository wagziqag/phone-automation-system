"""
auto_entity.py — Yyds.Auto 数据实体类定义
定义 OCR/YOLO/UI匹配/图像匹配等操作返回的结构化对象。
"""

from typing import Optional, Tuple


class Point:
    """坐标点"""
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

    def __iter__(self):
        return iter((self.x, self.y))

    @property
    def xy(self) -> tuple:
        return (self.x, self.y)


class BoundingBox:
    """矩形边界框"""
    def __init__(self, x1: int, y1: int, x2: int, y2: int):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @property
    def center_point(self) -> Point:
        cx, cy = self.center
        return Point(cx, cy)

    def __repr__(self):
        return f"BoundingBox({self.x1},{self.y1},{self.x2},{self.y2})"


class OcrResult:
    """OCR 识别结果"""
    def __init__(self, text: str, cx: int, cy: int,
                 x1: int, y1: int, x2: int = 0, y2: int = 0,
                 x3: int = 0, y3: int = 0, x4: int = 0, y4: int = 0,
                 prob: float = 1.0):
        self.text = text
        self.cx = cx
        self.cy = cy
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2 or x3
        self.y2 = y2 or y1
        self.x3 = x3 or x2
        self.y3 = y3 or y4
        self.x4 = x4 or x1
        self.y4 = y4 or y3
        self.prob = prob
        self.bounds = BoundingBox(x1, y1, self.x3 or x2, self.y3 or y4)

    def __repr__(self):
        return f'OcrResult(text="{self.text}", cx={self.cx}, cy={self.cy}, prob={self.prob:.2f})'


class ImageResult:
    """图像模板匹配结果"""
    def __init__(self, name: str, prob: float,
                 cx: int, cy: int, x: int, y: int,
                 width: int, height: int):
        self.name = name
        self.prob = prob
        self.cx = cx
        self.cy = cy
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.bounds = BoundingBox(x, y, x + width, y + height)

    def __repr__(self):
        return f'ImageResult(name="{self.name}", cx={self.cx}, cy={self.cy}, prob={self.prob:.2f})'


class UiNode:
    """UI 树节点"""
    def __init__(self, class_name: str = "", text: str = "",
                 desc: str = "", node_id: str = "",
                 bounds: Optional[dict] = None, bound_str: str = "",
                 center: Optional[Tuple[int, int]] = None,
                 children: Optional[list] = None):
        self.class_name = class_name
        self.text = text
        self.desc = desc
        self.id = node_id
        self.bound_str = bound_str
        self.children = children or []
        if bounds:
            self.bounds = BoundingBox(
                bounds.get("x1", 0), bounds.get("y1", 0),
                bounds.get("x2", 0), bounds.get("y2", 0)
            )
        else:
            # 从 bound_str 解析 "[x1,y1][x2,y2]"
            self.bounds = BoundingBox(0, 0, 0, 0)
            if bound_str:
                try:
                    import re
                    nums = re.findall(r'\d+', bound_str)
                    if len(nums) >= 4:
                        self.bounds = BoundingBox(
                            int(nums[0]), int(nums[1]),
                            int(nums[2]), int(nums[3])
                        )
                except Exception:
                    pass
        if center:
            self._center = Point(*center)
        else:
            self._center = self.bounds.center_point

    @property
    def center_point(self) -> Tuple[int, int]:
        return self._center.xy

    def __repr__(self):
        label = self.text or self.desc or self.class_name or "Node"
        return f'UiNode("{label}")'


class YoloResult:
    """YOLO 目标检测结果"""
    def __init__(self, label: str, prob: float,
                 cx: int, cy: int, x: int, y: int,
                 w: int, h: int):
        self.label = label
        self.prob = prob
        self.cx = cx
        self.cy = cy
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.width = w
        self.height = h
        self.bounds = BoundingBox(x, y, x + w, y + h)

    def __repr__(self):
        return f'YoloResult(label="{self.label}", cx={self.cx}, cy={self.cy}, prob={self.prob:.2f})'


# 导出所有类型
__all__ = [
    "Point", "BoundingBox",
    "OcrResult", "ImageResult", "UiNode", "YoloResult",
]
