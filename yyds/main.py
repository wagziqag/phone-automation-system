"""
main.py — Yyds.Auto 工程入口

支持模式：
  - 直接运行: python main.py → 启动轮询器
  - 测试模式: python main.py test → 运行内置测试
  - 单命令: python main.py click 540 1200 → 执行单命令
"""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1]

        if mode == "test":
            # 内置测试
            print("=== Yyds.Auto Test ===")
            from yyds.auto_api import device_model, device_get_screen_size, device_foreground_activity
            print(f"Device: {device_model()}")
            print(f"Screen: {device_get_screen_size()}")
            print(f"Foreground: {device_foreground_activity()}")
            print("=== Test OK ===")

        elif mode == "status":
            # 状态报告
            from yyds.auto_api import device_model, device_get_screen_size, device_foreground_activity
            from yyds.auto_api_aux import screen_ocr_x
            import json
            report = {
                "model": device_model(),
                "screen": device_get_screen_size(),
                "foreground": device_foreground_activity(),
                "ocr_lines": len(screen_ocr_x()),
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))

        elif mode == "click" and len(sys.argv) >= 4:
            from yyds.auto_api import click
            x, y = int(sys.argv[2]), int(sys.argv[3])
            click(x, y)
            print(f"Clicked ({x}, {y})")

        elif mode == "ocr":
            from yyds.auto_api_aux import screen_ocr_x
            results = screen_ocr_x()
            for r in results:
                print(f"  [{r.prob:.2f}] {r.text:20s} @ ({r.cx},{r.cy})")

        elif mode == "poll":
            # 启动轮询器
            from yyds.yyds_executor import main as executor_main
            executor_main()

        else:
            print(f"Unknown mode: {mode}")
            print("Available: test, status, click <x> <y>, ocr, poll")

    else:
        # 默认：启动轮询器
        print("Starting Yyds.Auto Executor (poll mode)...")
        from yyds.yyds_executor import main as executor_main
        executor_main()
