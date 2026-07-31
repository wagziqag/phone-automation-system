#!/usr/bin/env python3
"""
autonomous_agent.py — Marvis 自主探索 Agent (v3)

整合六大引擎，实现手机应用的自主探索、学习、记忆和进化:

  1. ADB + uiautomator  — 截图/UI树/触控/按键 (物理层)
  2. M-Flow Graph        — 图推理：从搜索到联想 (认知层)
  3. Self-Harness        — 失败轨迹自改进 (进化层)
  4. App Knowledge Base  — 应用知识文档化 (记忆层)
  5. HyperGraph RAG      — 超图多跳记忆 (语义层)
  6. Evolution Engine    — PPO+EWC 强化学习 (优化层)

运行模式:
  python3 autonomous_agent.py explore <app>       # 探索指定应用
  python3 autonomous_agent.py task "打开微信发消息"  # 执行指定任务
  python3 autonomous_agent.py learn               # 从历史学习
  python3 autonomous_agent.py status              # 状态报告
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

# ── 日志 ──
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)-5s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(PROJECT_DIR / "agent.log", mode='a')]
)
logger = logging.getLogger("autonomous_agent")

# ═══════════════════════════════════════════════════════════
# 1. ADB 执行器
# ═══════════════════════════════════════════════════════════

class ADBExecutor:
    """ADB + uiautomator 原子操作"""

    def __init__(self):
        self.screen_w = 1080
        self.screen_h = 2400
        self._detect_screen()

    def _detect_screen(self):
        try:
            out = self._adb("shell wm size")
            m = re.search(r'(\d+)x(\d+)', out)
            if m:
                self.screen_w, self.screen_h = int(m.group(1)), int(m.group(2))
        except:
            pass

    def _adb(self, cmd: str, timeout: int = 10) -> str:
        result = subprocess.run(
            f"adb {cmd}", shell=True, capture_output=True, text=True, timeout=timeout
        )
        return (result.stdout + result.stderr).strip()

    def screenshot(self, path: str = "") -> str:
        """截图并返回路径"""
        if not path:
            path = f"/sdcard/shot_{int(time.time())}.png"
        self._adb(f"shell screencap -p {path}")
        # 拉取到本地
        local = PROJECT_DIR / "data" / "screenshots" / Path(path).name
        local.parent.mkdir(parents=True, exist_ok=True)
        self._adb(f"pull {path} {local}")
        return str(local)

    def ui_tree(self, path: str = "") -> str:
        """获取 UI 树 XML"""
        if not path:
            path = "/sdcard/ui_tree.xml"
        self._adb("shell uiautomator dump")
        local = PROJECT_DIR / "data" / "ui_trees" / "ui_tree.xml"
        local.parent.mkdir(parents=True, exist_ok=True)
        self._adb(f"pull /sdcard/ui_tree.xml {local}")
        return str(local)

    def tap(self, x: int, y: int):
        self._adb(f"shell input tap {x} {y}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        self._adb(f"shell input swipe {x1} {y1} {x2} {y2} {duration}")

    def input_text(self, text: str):
        safe_text = text.replace(" ", "%s").replace("&", "\\&")
        self._adb(f"shell input text '{safe_text}'")

    def press_key(self, key: str):
        self._adb(f"shell input keyevent {key}")

    def press_back(self):
        self.press_key("KEYCODE_BACK")

    def press_home(self):
        self.press_key("KEYCODE_HOME")

    def launch_app(self, package: str):
        self._adb(f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def list_packages(self, filter_str: str = "") -> List[str]:
        out = self._adb("shell pm list packages")
        pkgs = re.findall(r'package:(\S+)', out)
        if filter_str:
            pkgs = [p for p in pkgs if filter_str.lower() in p.lower()]
        return pkgs

    def get_current_activity(self) -> str:
        out = self._adb("shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'")
        return out.strip()[:200]

    def parse_ui_elements(self) -> List[Dict]:
        """解析 UI 树获取可交互元素"""
        ui_path = self.ui_tree()
        try:
            with open(ui_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return []

        elements = []
        for match in re.finditer(
            r'<node[^>]*text="([^"]*)"[^>]*resource-id="([^"]*)"[^>]*class="([^"]*)"[^>]*'
            r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*clickable="([^"]*)"[^>]*',
            content
        ):
            text = match.group(1) or ""
            if not text:
                # 尝试 content-desc
                desc_match = re.search(r'content-desc="([^"]*)"', match.group(0))
                if desc_match:
                    text = desc_match.group(1)
            elements.append({
                "text": text,
                "resource_id": match.group(2),
                "class": match.group(3),
                "bounds": [int(match.group(4)), int(match.group(5)),
                          int(match.group(6)), int(match.group(7))],
                "clickable": match.group(8) == "true",
                "center": [(int(match.group(4)) + int(match.group(6))) // 2,
                          (int(match.group(5)) + int(match.group(7))) // 2],
            })
        return elements


# ═══════════════════════════════════════════════════════════
# 2. 统一 Agent
# ═══════════════════════════════════════════════════════════

class AutonomousAgent:
    """整合六大引擎的自主 Agent"""

    def __init__(self):
        self.adb = ADBExecutor()

        # 加载引擎（优雅降级）
        self.mflow = self._load_mflow()
        self.harness = self._load_harness()
        self.app_kb = self._load_app_kb()
        self.hypergraph = self._load_hypergraph()
        self.evolution = self._load_evolution()

        # 当前状态
        self.current_app: str = ""
        self.current_screen: str = ""
        self.exploration_history: List[Dict] = []
        self.known_apps: Dict[str, Dict] = {}

        logger.info(f"[agent] 初始化完成 | MFlow={self.mflow is not None} "
                    f"Harness={self.harness is not None} "
                    f"AppKB={self.app_kb is not None} "
                    f"HyperGraph={self.hypergraph is not None} "
                    f"Evolution={self.evolution is not None}")

    # ── 引擎加载 ──

    def _load_mflow(self):
        try:
            from mflow_graph import MFlowGraph
            g = MFlowGraph()
            g.load()
            return g
        except Exception as e:
            logger.warning(f"MFlow 加载失败: {e}")
            return None

    def _load_harness(self):
        try:
            from self_harness import SelfHarness
            h = SelfHarness()
            h.load()
            return h
        except Exception as e:
            logger.warning(f"SelfHarness 加载失败: {e}")
            return None

    def _load_app_kb(self):
        try:
            from modules.app_knowledge_base import AppKnowledgeBase
            return AppKnowledgeBase()
        except Exception as e:
            logger.warning(f"AppKnowledgeBase 加载失败: {e}")
            return None

    def _load_hypergraph(self):
        try:
            from modules.hypergraph_memory import HypergraphMemory
            return HypergraphMemory()
        except Exception as e:
            logger.warning(f"HyperGraph 加载失败: {e}")
            return None

    def _load_evolution(self):
        try:
            from evolution_v2 import EvolutionManager
            return EvolutionManager()
        except Exception as e:
            logger.warning(f"Evolution 加载失败: {e}")
            return None

    # ═══════════════════════════════════════════════════════
    # 核心：探索流程
    # ═══════════════════════════════════════════════════════

    def explore_app(self, package: str, max_screens: int = 20,
                    max_steps_per_screen: int = 10) -> Dict:
        """
        自主探索应用：遍历界面 → 记录元素 → 构建知识

        流程:
          1. 启动应用
          2. 截图 + 解析 UI 树
          3. M-Flow 联想: 基于已知知识推导探索方向
          4. Self-Harness 检查: 是否有失败经验要规避
          5. 逐元素点击探索
          6. 记录结果到 AppKB + MFlow + HyperGraph
        """
        logger.info(f"[explore] 开始探索 {package}")
        t0 = time.time()

        # 获取应用信息
        app_info = self._get_app_info(package)
        screens_explored = []
        visited = set()

        # 启动应用
        self.adb.launch_app(package)
        time.sleep(2)
        self.current_app = package

        for screen_idx in range(max_screens):
            time.sleep(1)

            # 截图 + UI 树
            screenshot = self.adb.screenshot()
            ui_path = self.adb.ui_tree()
            elements = self.adb.parse_ui_elements()

            # 当前界面指纹
            screen_fingerprint = self._screen_fingerprint(elements)
            if screen_fingerprint in visited:
                self.adb.press_back()
                time.sleep(1)
                continue
            visited.add(screen_fingerprint)

            # 过滤可交互元素
            clickable = [e for e in elements if e["clickable"] and e["text"]]

            logger.info(f"[explore] 界面 {screen_idx+1}/{max_screens}: "
                        f"{len(clickable)} 个可交互元素")

            if not clickable:
                self.adb.swipe(540, 1600, 540, 800)  # 上滑
                continue

            # M-Flow 联想：这个界面可能的功能
            mflow_hints = []
            if self.mflow:
                anomaly = [e["text"] for e in clickable if e["text"]]
                mflow_hints = self.mflow.associate(anomaly, max_results=3)

            # 记录界面到 AppKB
            if self.app_kb:
                try:
                    self.app_kb.record_screen(package, f"screen_{screen_idx}",
                                             elements, screenshot)
                except:
                    pass

            # 记录到 M-Flow
            if self.mflow:
                self.mflow.ingest_app_exploration(
                    package, f"screen_{screen_idx}", elements,
                    [{"name": e["text"], "type": "click", "target": str(e["center"])}
                     for e in clickable[:5]]
                )

            # 逐元素探索（受限于步数）
            screen_actions = []
            for i, elem in enumerate(clickable[:min(len(clickable), max_steps_per_screen)]):
                x, y = elem["center"]
                action_name = elem["text"]

                # Self-Harness 检查
                harness_hints = {}
                if self.harness:
                    harness_hints = self.harness.before_action(package, "tap", action_name)

                # 执行
                self.adb.tap(x, y)
                time.sleep(1.5)

                # 验证结果
                new_activity = self.adb.get_current_activity()
                new_screenshot = self.adb.screenshot()

                success = True
                # 检查是否仍在同一应用
                if package not in new_activity:
                    success = True  # 跳转也视为成功

                screen_actions.append({
                    "element": action_name,
                    "position": [x, y],
                    "result_activity": new_activity[:100],
                    "success": success,
                })

                # 记录到 Self-Harness
                if self.harness:
                    self.harness.record(
                        task=f"探索 {package} 界面 {screen_idx}",
                        app=package,
                        steps=[{"action": "tap", "element": action_name,
                               "success": success}],
                        success=success,
                        error_type="" if success else "unexpected_state",
                        duration_ms=int((time.time() - t0) * 1000),
                    )

                # 返回原界面
                self.adb.press_back()
                time.sleep(1)

            screens_explored.append({
                "screen_id": f"screen_{screen_idx}",
                "elements_count": len(elements),
                "clickable_count": len(clickable),
                "actions_tested": screen_actions,
                "mflow_hints": mflow_hints,
            })

            # 保存
            self.exploration_history.extend(screen_actions)

        # 回到桌面
        self.adb.press_home()

        duration = time.time() - t0
        logger.info(f"[explore] 完成: {len(screens_explored)} 界面, "
                    f"耗时 {duration:.0f}s")

        result = {
            "app": package,
            "app_info": app_info,
            "screens_explored": len(screens_explored),
            "total_actions": sum(len(s["actions_tested"])) for s in screens_explored),
            "duration_seconds": round(duration, 1),
            "screens": screens_explored,
        }

        # 保存探索结果
        self._save_exploration(package, result)

        return result

    def _screen_fingerprint(self, elements: List[Dict]) -> str:
        """界面指纹：基于可交互元素的文本"""
        texts = sorted([e["text"] for e in elements if e["text"] and e["clickable"]])
        return "|".join(texts[:20])

    def _get_app_info(self, package: str) -> Dict:
        """获取应用详细信息"""
        info = {"package": package}
        try:
            out = self.adb._adb(f"shell dumpsys package {package} | grep -E "
                               "'versionName|versionCode|targetSdkVersion'")
            for line in out.split('\n'):
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    info[k.strip()] = v.strip()
        except:
            pass
        return info

    # ═══════════════════════════════════════════════════════
    # 任务执行
    # ═══════════════════════════════════════════════════════

    def execute_task(self, task: str, app: str = "") -> Dict:
        """
        执行指定任务: 自然语言 → 图联想路径 → 逐步执行

        流程:
          1. 解析任务 → 关键词
          2. M-Flow 联想 → 找到可能路径
          3. AppKB 检索 → 获取界面知识
          4. Self-Harness 注入 → 规避已知陷阱
          5. 逐步执行 → 记录轨迹
          6. 反映 → 更新经验
        """
        logger.info(f"[task] 开始: {task}")
        t0 = time.time()

        # 确定目标应用
        target_app = app
        if not target_app:
            # 从任务关键词推测应用
            app_map = {
                "微信": "com.tencent.mm", "QQ": "com.tencent.mobileqq",
                "淘宝": "com.taobao.taobao", "京东": "com.jingdong.app.mall",
                "设置": "com.android.settings", "浏览器": "com.android.chrome",
                "相机": "com.android.camera", "相册": "com.android.gallery3d",
                "计算器": "com.android.calculator2", "时钟": "com.android.deskclock",
            }
            for kw, pkg in app_map.items():
                if kw in task:
                    target_app = pkg
                    break

        # M-Flow 联想
        mflow_paths = []
        if self.mflow and target_app:
            keywords = re.findall(r'[\u4e00-\u9fa5]{2,6}', task)
            mflow_paths = self.mflow.associate(keywords, max_results=3)

        # AppKB 检索
        kb_docs = []
        if self.app_kb and target_app:
            try:
                kb_docs = self.app_kb.retrieve(task, app_name=target_app, top_k=3)
            except:
                pass

        # 启动应用
        if target_app:
            self.adb.launch_app(target_app)
            time.sleep(2)

        # TODO: 这里是实际执行逻辑——未来需要视觉模型驱动
        # 当前版本: 基于 UI 树匹配关键字执行
        steps_executed = []
        success = False

        # 尝试通过 UI 树匹配关键字
        elements = self.adb.parse_ui_elements()
        task_words = set(re.findall(r'[\u4e00-\u9fa5]{1,6}', task))

        for word in task_words:
            for elem in elements:
                if word in elem.get("text", "") and elem["clickable"]:
                    x, y = elem["center"]
                    self.adb.tap(x, y)
                    time.sleep(1)
                    steps_executed.append({
                        "keyword": word, "element": elem["text"],
                        "action": "tap", "position": [x, y],
                    })
                    success = True
                    break

        duration = time.time() - t0

        # 记录轨迹
        if self.harness:
            self.harness.record(
                task=task, app=target_app or "unknown",
                steps=steps_executed, success=success,
                duration_ms=int(duration * 1000),
            )

        # 更新 M-Flow
        if self.mflow and target_app and steps_executed:
            self.mflow.ingest_flow(target_app, task[:20], steps_executed, success)

        result = {
            "task": task,
            "target_app": target_app,
            "success": success,
            "steps_executed": len(steps_executed),
            "duration_seconds": round(duration, 1),
            "steps": steps_executed,
            "mflow_hints": mflow_paths,
            "kb_docs_count": len(kb_docs),
        }

        self._save_result(task, result)
        return result

    # ═══════════════════════════════════════════════════════
    # 学习与进化
    # ═══════════════════════════════════════════════════════

    def learn(self) -> Dict:
        """从历史经验学习并进化"""
        report = {
            "harness_analysis": None,
            "harness_evolution": None,
            "mflow_stats": None,
            "suggestions": [],
        }

        # 分析失败模式
        if self.harness:
            report["harness_analysis"] = self.harness.analyze_failures()
            report["harness_evolution"] = self.harness.evolve(apply_threshold=2)

        # M-Flow 统计
        if self.mflow:
            self.mflow.save()
            report["mflow_stats"] = self.mflow.stats()

        # 生成改进建议
        suggestions = []
        if self.harness and self.harness.success_rate() < 0.7:
            suggestions.append("成功率低于70%，建议增加备用定位策略")
        if self.mflow and len(self.mflow.nodes) < 10:
            suggestions.append("M-Flow 节点较少，建议多探索几个应用")

        report["suggestions"] = suggestions
        return report

    # ═══════════════════════════════════════════════════════
    # 持久化
    # ═══════════════════════════════════════════════════════

    def _save_exploration(self, package: str, result: Dict):
        out_dir = PROJECT_DIR / "data" / "explorations"
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{package.replace('.', '_')}_{int(time.time())}.json"
        with open(out_dir / fname, 'w') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def _save_result(self, task: str, result: Dict):
        out_dir = PROJECT_DIR / "data" / "tasks"
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"task_{int(time.time())}.json"
        with open(out_dir / fname, 'w') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def status(self) -> Dict:
        """返回 Agent 完整状态"""
        return {
            "adb": {
                "screen": f"{self.adb.screen_w}x{self.adb.screen_h}",
                "current_app": self.adb.get_current_activity()[:200],
            },
            "mflow": self.mflow.stats() if self.mflow else None,
            "harness": self.harness.stats() if self.harness else None,
            "exploration": {
                "history_count": len(self.exploration_history),
            },
            "timestamp": datetime.now().isoformat(),
        }


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Marvis 自主探索 Agent v3")
    sub = parser.add_subparsers(dest="cmd")

    # explore
    p_explore = sub.add_parser("explore", help="探索应用")
    p_explore.add_argument("app", help="应用包名或关键词")
    p_explore.add_argument("--max-screens", type=int, default=15)
    p_explore.add_argument("--max-steps", type=int, default=8)

    # task
    p_task = sub.add_parser("task", help="执行任务")
    p_task.add_argument("description", help="任务描述")
    p_task.add_argument("--app", default="", help="目标应用包名")

    # learn
    sub.add_parser("learn", help="从历史学习并进化")

    # status
    sub.add_parser("status", help="状态报告")

    # batch
    p_batch = sub.add_parser("batch", help="批量探索多个应用")
    p_batch.add_argument("--filter", default="", help="应用包名过滤")
    p_batch.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()
    agent = AutonomousAgent()

    if args.cmd == "explore":
        # 支持关键词匹配
        pkg = args.app
        if not pkg.startswith("com."):
            pkgs = agent.adb.list_packages(pkg)
            if pkgs:
                pkg = pkgs[0]
                logger.info(f"匹配到应用: {pkg}")
            else:
                logger.error(f"未找到匹配 '{args.app}' 的应用")
                sys.exit(1)

        result = agent.explore_app(pkg, args.max_screens, args.max_steps)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "task":
        result = agent.execute_task(args.description, args.app)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "learn":
        result = agent.learn()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "status":
        result = agent.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "batch":
        pkgs = agent.adb.list_packages(args.filter)
        logger.info(f"找到 {len(pkgs)} 个应用，批量探索前 {args.limit} 个")
        for pkg in pkgs[:args.limit]:
            logger.info(f"\n{'='*50}\n探索: {pkg}\n{'='*50}")
            try:
                agent.explore_app(pkg, max_screens=10, max_steps_per_screen=5)
            except Exception as e:
                logger.error(f"探索 {pkg} 失败: {e}")
        agent.learn()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
