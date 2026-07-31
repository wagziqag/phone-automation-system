import os
#!/usr/bin/env python3
"""元宝OCR方案对比 - 使用 ocr_pipeline 统一流水线"""
import sys, os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phone_system.ocr_pipeline import OCRPipeline

SS = "/sdcard/yb_reply2.png"
if not os.path.exists(SS):
    import subprocess as sp
    sp.run(["screencap", "-p", SS], timeout=5)

pipe = OCRPipeline()
res = pipe.run(SS, upload=True)
print(pipe.summary(res))
