"""
AssistantApp —— 手机自动化助手统一入口

整合所有模块：设备管理、自主探索、演示学习、模型微调、自主进化、
VTuber 互动、后台守护、Web API。

启动模式:
  python assistant_app.py                        # 默认: API + Daemon
  python assistant_app.py --mode explore         # 自主探索模式
  python assistant_app.py --mode demo            # 演示学习模式
  python assistant_app.py --mode tune            # 模型微调模式
  python assistant_app.py --mode evolve          # 自主进化模式
  python assistant_app.py --mode vtuber          # VTuber 服务模式
  python assistant_app.py --mode full            # 全功能模式
  python assistant_app.py --mode status          # 查看状态
"""

from __future__ import annotations

import argparse
# asyncio removed (sync mode)
import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-18s] %(levelname)-7s %(message)s",
)
logger = logging.getLogger("AssistantApp")


# ============================================================
# 配置
# ============================================================

@dataclass
class AppConfig:
    """应用配置"""
    # ADB
    adb_path: str = "adb"
    device_serial: str = ""                 # 空=自动选择

    # Ollama
    ollama_url: str = "http://127.0.0.1:11434"
    base_model: str = "qwen3.5:2b-q4_K_M"
    vision_model: str = "qwen3.5:2b-q4_K_M"

    # 探索
    explore_app: str = ""                   # 探索目标应用
    explore_max_depth: int = 8
    explore_max_nodes: int = 100
    explore_timeout: int = 300              # 秒

    # 演示
    demo_duration: int = 120                # 录制时长
    demo_task: str = ""                     # 任务描述
    demo_output: str = ""                   # 导出路径

    # 微调
    finetune_dataset: str = ""              # 训练数据路径
    finetune_model_name: str = ""           # 输出模型名

    # 进化
    evolution_dir: str = "./data/evolution"
    evolution_min_samples: int = 50
    evolution_interval: int = 30            # 分钟
    evolution_auto_deploy: bool = True

    # VTuber
    vtuber_host: str = "0.0.0.0"
    vtuber_port: int = 8000
    vtuber_personality: str = "friendly"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    # Daemon
    daemon_enabled: bool = True
    daemon_heartbeat_interval: int = 5

    # 路径
    data_dir: str = "./data"
    output_dir: str = "./output"
    static_dir: str = "./static"

    def save(self, filepath: str):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, default=str),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, filepath: str) -> "AppConfig":
        data = json.loads(Path(filepath).read_text())
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}
        return cls(**data)


# ============================================================
# 模块初始化
# ============================================================

class ModuleRegistry:
    """
    模块注册表 —— 统一管理所有模块的生命周期。
    支持部分加载（某个模块依赖缺失时不影响其他模块）。
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self._modules: Dict[str, Any] = {}
        self._status: Dict[str, str] = {}   # ok / degraded / failed / disabled

    def _register(self, name: str, instance: Any, status: str = "ok"):
        self._modules[name] = instance
        self._status[name] = status

    def get(self, name: str, default=None):
        return self._modules.get(name, default)

    @property
    def all_ok(self) -> bool:
        return all(s in ("ok", "degraded") for s in self._status.values())

    def status_report(self) -> Dict[str, Any]:
        return {
            name: {
                "status": self._status.get(name, "unknown"),
                "type": type(self._modules.get(name, None)).__name__ if self._modules.get(name) else "None",
            }
            for name in sorted(set(list(self._status.keys()) + list(self._modules.keys())))
        }


def init_modules(config: AppConfig) -> ModuleRegistry:
    """初始化所有模块"""
    reg = ModuleRegistry(config)

    # ======== VectorMemory ========
    try:
        from modules.vector_memory import VectorMemory
        mem_dir = Path(config.data_dir) / "chroma"
        mem_dir.mkdir(parents=True, exist_ok=True)
        mem = VectorMemory(persist_dir=str(mem_dir))
        reg._register("vector_memory", mem)
        logger.info("[memory   ] 向量记忆就绪")
    except Exception as e:
        logger.warning(f"[memory   ] 不可用: {e}")
        reg._register("vector_memory", None, "failed")

    # ======== DeviceRegistry ========
    try:
        from modules.device_registry import DeviceRegistry
        registry = DeviceRegistry(registry_file=str(Path(config.data_dir) / "device_registry.json"))
        reg._register("device_registry", registry)
        registry.scan_and_register()
        logger.info("[device   ] 设备注册表就绪")
    except Exception as e:
        logger.warning(f"[device   ] 不可用: {e}")
        reg._register("device_registry", None, "failed")

    # ======== PhoneController ========
    try:
        from modules.phone_controller import PhoneController, ActionResult, ActionType
        ctrl = PhoneController(
            adb_path=config.adb_path,
            device_serial=config.device_serial,
            ollama_url=config.ollama_url,
            vision_model=config.vision_model,
            text_model=config.base_model,
        )
        reg._register("phone_controller", ctrl)
        logger.info("[phone    ] 手机控制器就绪")
    except Exception as e:
        logger.warning(f"[phone    ] 不可用: {e}")
        reg._register("phone_controller", None, "failed")

    # ======== AutonomousExplorer ========
    ctrl = reg.get("phone_controller")
    if ctrl:
        try:
            from modules.autonomous_explorer import AutonomousExplorer, ExplorationConfig
            explorer = AutonomousExplorer(
                controller=ctrl,
                config=ExplorationConfig(
                    ollama_url=config.ollama_url,
                    model=config.vision_model,
                ),
            )
            reg._register("autonomous_explorer", explorer)
            logger.info("[explorer ] 自主探索器就绪")
        except Exception as e:
            logger.warning(f"[explorer ] 不可用: {e}")
            reg._register("autonomous_explorer", None, "degraded")
    else:
        reg._register("autonomous_explorer", None, "disabled")

    # ======== DemoRecorder + PatternLearner ========
    if ctrl:
        try:
            from modules.demo_learner import DemoRecorder, PatternLearner, KnowledgeBase
            demo_dir = Path(config.data_dir) / "demos"
            demo_dir.mkdir(parents=True, exist_ok=True)
            recorder = DemoRecorder(ctrl, demo_dir)
            reg._register("demo_recorder", recorder)
            kb_dir = Path(config.data_dir) / "knowledge"
            kb_dir.mkdir(parents=True, exist_ok=True)
            kb = KnowledgeBase(data_dir=kb_dir)
            learner = PatternLearner(kb, ollama_url=config.ollama_url)
            reg._register("demo_learner", learner)
            logger.info("[demo     ] DemoRecorder + PatternLearner 就绪")
        except Exception as e:
            logger.warning(f"[demo     ] 不可用: {e}")
            reg._register("demo_learner", None, "degraded")
    else:
        reg._register("demo_learner", None, "disabled")

    # ======== ModelFinetuner ========
    try:
        from modules.model_finetuner import ModelFinetuner
        tuner = ModelFinetuner(
            ollama_url=config.ollama_url,
            output_dir=str(Path(config.data_dir) / "finetune"),
        )
        reg._register("model_finetuner", tuner)
        logger.info("[tuner    ] 模型微调器就绪")
    except Exception as e:
        logger.warning(f"[tuner    ] 不可用: {e}")
        reg._register("model_finetuner", None, "failed")

    # ======== PreferenceStore（偏好记忆） ========
    try:
        from modules.preference_store import get_preference_store
        prefs = get_preference_store()
        reg._register("preference_store", prefs)
        logger.info("[prefs    ] 偏好记忆库就绪")
    except Exception as e:
        logger.warning(f"[prefs    ] 不可用: {e}")
        reg._register("preference_store", None, "failed")

    # ======== AutoEvolution ========
    tuner = reg.get("model_finetuner")
    if tuner:
        try:
            from modules.auto_evolution import (
                AutoEvolution, EvolutionConfig, DataCollector, MetricTracker,
            )
            evo_config = EvolutionConfig(
                data_dir=str(Path(config.data_dir) / "evolution"),
                min_samples=config.evolution_min_samples,
                auto_deploy=config.evolution_auto_deploy,
            )
            evolution = AutoEvolution(
                tuner=tuner,
                base_model=config.base_model,
                config=evo_config,
            )
            reg._register("auto_evolution", evolution)
            reg._register("data_collector", evolution.collector)
            reg._register("metric_tracker", evolution.tracker)
            logger.info("[evolution] 自主进化系统就绪")
        except Exception as e:
            logger.warning(f"[evolution] 不可用: {e}")
            reg._register("auto_evolution", None, "failed")
    else:
        reg._register("auto_evolution", None, "disabled")
        reg._register("data_collector", None, "disabled")
        reg._register("metric_tracker", None, "disabled")

    # ======== SearXNG + ntfy ========
    try:
        from modules.searxng import SearXNGClient
        searxng = SearXNGClient()
        reg._register("searxng", searxng)
        logger.info("[search   ] SearXNG 就绪")
    except Exception:
        reg._register("searxng", None, "degraded")

    try:
        from modules.ntfy_client import NtfyClient
        ntfy = NtfyClient()
        reg._register("ntfy", ntfy)
        logger.info("[notify   ] ntfy 就绪")
    except Exception:
        reg._register("ntfy", None, "degraded")

    # ======== AssistantDaemon ========
    if config.daemon_enabled:
        try:
            from modules.assistant_daemon import AssistantDaemon, DaemonConfig
            dc = DaemonConfig(heartbeat_interval=config.daemon_heartbeat_interval)
            daemon = AssistantDaemon(config=dc)
            reg._register("daemon", daemon)
            logger.info("[daemon   ] 守护进程就绪")
        except Exception as e:
            logger.warning(f"[daemon   ] 不可用: {e}")
            reg._register("daemon", None, "failed")

    # ======== AssistantAPI ========
    try:
        from modules.assistant_api import AssistantAPI, TaskType
        api = AssistantAPI(
            daemon=reg.get("daemon"),
            registry=reg.get("device_registry"),
            vector_memory=reg.get("vector_memory"),
            static_dir=config.static_dir,
        )

        # 注册 phone_automation 任务处理器
        phone_ctrl = reg.get("phone_controller")

        def _ensure_task_app_foreground(ctrl, goal: str):
            """从任务目标中检测应用名并确保其在前台"""
            # 常见中文应用名 → 包名映射
            APP_MAP = {
                "抖音": "com.ss.android.ugc.aweme",
                "快手": "com.smile.gifmaker",
                "微信": "com.tencent.mm",
                "QQ": "com.tencent.mobileqq",
                "淘宝": "com.taobao.taobao",
                "京东": "com.jingdong.app.mall",
                "小红书": "com.xingin.xhs",
                "B站": "tv.danmaku.bili",
                "哔哩哔哩": "tv.danmaku.bili",
                "bilibili": "tv.danmaku.bili",
                "知乎": "com.zhihu.android",
                "百度": "com.baidu.searchbox",
                "美团": "com.sankuai.meituan",
                "拼多多": "com.xunmeng.pinduoduo",
                "今日头条": "com.ss.android.article.news",
                "微博": "com.sina.weibo",
                "网易云音乐": "com.netease.cloudmusic",
                "酷狗": "com.kugou.android",
                "QQ音乐": "com.tencent.qqmusic",
                "高德地图": "com.autonavi.minimap",
                "闲鱼": "com.taobao.idlefish",
            }
            detected_pkg = None
            for name, pkg in APP_MAP.items():
                if name.lower() in goal.lower():
                    detected_pkg = pkg
                    break

            if not detected_pkg:
                return None

            logger.info(f"[handler  ] 检测到目标应用: {detected_pkg}")
            # 检查当前前台
            current = ctrl.get_current_app()
            if current and detected_pkg in current:
                logger.info(f"[handler  ] {detected_pkg} 已在前台")
                return detected_pkg

            # 启动并验证
            logger.info(f"[handler  ] 启动 {detected_pkg}...")
            ctrl.launch_app(detected_pkg)
            is_fg, fg_app = ctrl.ensure_foreground(detected_pkg, max_wait=10, retries=3)
            if is_fg:
                logger.info(f"[handler  ] {detected_pkg} 启动成功")
                return detected_pkg
            else:
                logger.warning(
                    f"[handler  ] {detected_pkg} 启动后未检测到在前台 (当前: {fg_app or '未知'})"
                )
                return detected_pkg  # 仍然返回包名，让AI决策循环中再处理

        if phone_ctrl:

            def handle_phone_task(record):
                """执行手机自动化任务"""
                ctrl = phone_ctrl
                logger.info(f"[handler  ] 收到任务: {record.goal[:60]}")

                if not ctrl._connected:
                    ok = ctrl.connect()
                    if not ok:
                        record.error = "ADB 设备未连接"
                        logger.error(f"[handler  ] ADB 连接失败")
                        return None
                    logger.info(f"[handler  ] ADB 已连接: {ctrl.device_serial}")

                # 如果任务目标提到了应用名，先确保该应用在前台
                launched_pkg = _ensure_task_app_foreground(ctrl, record.goal)

                max_steps = getattr(record, 'params', {}).get("max_steps", 20)
                for step in range(max_steps):
                    state = ctrl.capture_state()
                    if state is None:
                        record.error = "截图或屏幕分析失败"
                        logger.error(f"[handler  ] 步骤{step+1} capture_state 失败")
                        return None

                    # 如果检测到前台应用跑偏，尝试恢复
                    if launched_pkg and step > 0 and step % 5 == 0:
                        current_pkg = ctrl.get_current_app()
                        if current_pkg and launched_pkg not in current_pkg:
                            logger.warning(
                                f"[handler  ] 前台应用偏移: 期望={launched_pkg}, 当前={current_pkg}"
                            )
                            is_ok, _ = ctrl.ensure_foreground(launched_pkg, max_wait=8, retries=2)
                            if not is_ok:
                                logger.error(f"[handler  ] 无法恢复 {launched_pkg} 到前台")

                    decision = ctrl.ai_decide_action(
                        record.goal, state, ctrl._action_history
                    )
                    if decision is None:
                        record.error = "AI 决策返回为空"
                        logger.error(f"[handler  ] 步骤{step+1} AI 决策为空")
                        return None

                    action = decision.get("action", "")
                    logger.info(f"[handler  ] 步骤{step+1}: {action}")
                    if action == "done":
                        return {"status": "completed", "steps": step + 1}

                    if action.startswith("fail"):
                        record.error = action
                        logger.error(f"[handler  ] 步骤{step+1} AI 判定失败: {action}")
                        return None

                    # 执行动作
                    parts = action.split("|")
                    action_type = parts[0]
                    try:
                        if action_type == "tap":
                            result = ctrl.tap(int(parts[1]), int(parts[2]))
                        elif action_type == "swipe":
                            result = ctrl.swipe(
                                int(parts[1]), int(parts[2]),
                                int(parts[3]), int(parts[4])
                            )
                        elif action_type == "input":
                            result = ctrl.input_text(parts[1])
                        elif action_type == "back":
                            result = ctrl.press_back()
                        elif action_type == "home":
                            result = ctrl.press_home()
                        elif action_type == "launch":
                            pkg = parts[1]
                            result = ctrl.launch_app(pkg)
                            # 验证前台
                            is_fg, fg_app = ctrl.ensure_foreground(pkg, max_wait=10, retries=3)
                            if is_fg:
                                launched_pkg = pkg
                                logger.info(f"[handler  ] {pkg} 已在运行")
                            else:
                                logger.error(
                                    f"[handler  ] {pkg} 未进入前台 (当前: {fg_app or '未知'})，"
                                    "强制停止后重试..."
                                )
                                ctrl.stop_app(pkg)
                                time.sleep(1.5)
                                ctrl.launch_app(pkg)
                                time.sleep(3)
                                is_fg2, fg_app2 = ctrl.ensure_foreground(pkg, max_wait=8, retries=2)
                                if is_fg2:
                                    launched_pkg = pkg
                                    logger.info(f"[handler  ] {pkg} 重试后成功进入前台")
                                else:
                                    logger.error(
                                        f"[handler  ] {pkg} 重试后仍未进入前台 (当前: {fg_app2 or '未知'})，继续尝试..."
                                    )
                        else:
                            result = ActionResult(
                                action=ActionType.WAIT, success=False,
                                error=f"未知动作: {action_type}"
                            )
                    except Exception as e:
                        result = ActionResult(
                            action=ActionType.WAIT, success=False, error=str(e)
                        )

                    if not result.success and step > 0:
                        logger.warning(f"[handler  ] 步骤 {step} 失败: {result.error}")

                return {"status": "max_steps_reached", "steps": max_steps}

            api.task_manager.register_handler(
                TaskType.PHONE_AUTOMATION, handle_phone_task
            )
            logger.info("[api      ] 已注册 phone_automation 处理器")
        else:
            logger.warning("[api      ] PhoneController 不可用，无法注册任务处理器")

        reg._register("api", api)
        logger.info("[api      ] FastAPI 就绪")
    except Exception as e:
        logger.warning(f"[api      ] 不可用: {e} （需要: pip install fastapi uvicorn websockets python-multipart）")
        reg._register("api", None, "failed")

    # ======== VisualLocator (视觉定位器) ========
    try:
        from modules.core.visual_locator import VisualLocator
        vl = VisualLocator(
            ollama_url=config.ollama_url,
            ollama_model=config.vision_model,
        )
        reg._register("visual_locator", vl)
        logger.info("[visloc   ] 视觉定位器就绪 (uiautomator + Ollama)")
    except Exception as e:
        logger.warning(f"[visloc   ] 不可用: {e}")
        reg._register("visual_locator", None, "failed")

    # ======== TriBrain 三脑融合 ========
    try:
        from modules.core.tribrain import get_pipeline, register_tribrain_endpoints
        tribrain = get_pipeline()
        reg._register("tribrain", tribrain)
        logger.info("[tribrain ] 三脑融合模块就绪 (KG + Wiki + Sync)")

        # 如果 API 模块已就绪，注册端点
        api = reg.get("api")
        if api and hasattr(api, 'app'):
            register_tribrain_endpoints(api.app, tribrain)
            logger.info("[tribrain ] API 端点已注册 (15 routes)")
    except Exception as e:
        logger.warning(f"[tribrain ] 不可用: {e}")
        reg._register("tribrain", None, "failed")

    return reg


def _analyze_trajectory(trajectory) -> dict:
    """分析录制轨迹，提取关键统计信息。"""
    steps = trajectory.steps if hasattr(trajectory, 'steps') else []
    if not steps:
        return {"total_steps": 0, "actions": {}, "duration_s": 0}

    action_counts = {}
    total_duration = 0.0
    for step in steps:
        action = getattr(step, 'action_type', getattr(step, 'action', 'unknown'))
        action_counts[action] = action_counts.get(action, 0) + 1
        total_duration += float(getattr(step, 'duration', 0))

    return {
        "total_steps": len(steps),
        "actions": action_counts,
        "duration_s": round(total_duration, 2),
        "app": getattr(trajectory, 'app_package', ''),
        "success_rate": sum(1 for s in steps if getattr(s, 'success', True)) / len(steps),
    }


# ============================================================
# 运行模式
# ============================================================

def run_explore(config: AppConfig, reg: ModuleRegistry):
    """自主探索模式"""
    explorer = reg.get("autonomous_explorer")
    if not explorer:
        logger.error("自主探索器不可用")
        return

    app = config.explore_app or input("请输入要探索的应用包名: ").strip()
    if not app:
        logger.error("未指定应用包名")
        return

    # 应用探索参数
    from modules.autonomous_explorer import ExplorationConfig as ExpCfg
    explorer.config.max_depth = config.explore_max_depth
    explorer.config.max_nodes = config.explore_max_nodes
    explorer.config.exploration_timeout = config.explore_timeout

    logger.info(f"开始探索: {app}")
    result = explorer.explore(app)

    # 保存结果
    ts = time.strftime("%Y%m%d_%H%M%S")
    output_path = Path(config.output_dir) / f"explore_{app}_{ts}.json"
    explorer.save_result(result, str(output_path))
    logger.info(f"探索完成: {result.total_nodes} 节点, {result.total_edges} 边, {len(result.errors)} 错误")
    logger.info(f"结果已保存: {output_path}")


def run_demo(config: AppConfig, reg: ModuleRegistry):
    """演示学习模式"""
    learner = reg.get("demo_learner")
    if not learner:
        logger.error("演示学习器不可用")
        return

    task = config.demo_task or input("请输入任务描述 (如'在微信发一条朋友圈'): ").strip()
    app_package = input("请输入应用包名 (如 com.tencent.mm): ").strip()

    logger.info(f"开始录制演示: {task}")

    trajectory = learner.record(
        task_description=task,
        app_package=app_package,
        duration=config.demo_duration,
    )

    # 学习模式
    if learner:
        demo_data = {"name": task, "steps": trajectory.steps if hasattr(trajectory, 'steps') else []}
        patterns = learner.learn_from_demo(demo_data)
        logger.info(f"学习到 {len(patterns)} 个模式")
    else:
        logger.warning("PatternLearner 不可用，跳过学习")

    # 分析轨迹
    analysis = _analyze_trajectory(trajectory)
    logger.info(f"\n轨迹分析:\n{json.dumps(analysis, indent=2, ensure_ascii=False)}")


def run_tune(config: AppConfig, reg: ModuleRegistry):
    """模型微调模式"""
    tuner = reg.get("model_finetuner")
    if not tuner:
        logger.error("模型微调器不可用")
        return

    dataset = config.finetune_dataset or input("请输入训练数据路径: ").strip()
    model_name = config.finetune_model_name or input("请输入模型名 (如 phone-assistant-v1): ").strip()

    logger.info(f"开始微调: {model_name}")

    result = tuner.finetune(
        dataset_path=dataset,
        base_model=config.base_model,
        model_name=model_name,
    )

    if result:
        logger.info(f"微调完成: {result}")
    else:
        logger.error("微调失败")


def run_evolve(config: AppConfig, reg: ModuleRegistry):
    """自主进化模式"""
    evolution = reg.get("auto_evolution")
    if not evolution:
        logger.error("自主进化系统不可用")
        return

    logger.info("启动自主进化循环...")
    try:
        evolution.run_evolution_loop(
            check_interval_minutes=config.evolution_interval,
        )
    except KeyboardInterrupt:
        logger.info("进化循环已停止")


def run_vtuber(config: AppConfig, reg: ModuleRegistry):
    """VTuber 服务模式"""
    try:
        import uvicorn
        from run_vtuber import create_app, VtuberConfig

        cfg = VtuberConfig(
            personality=config.vtuber_personality,
            model=config.base_model,
            ollama_url=config.ollama_url,
            host=config.vtuber_host,
            port=config.vtuber_port,
            no_proactive=False,
            static_dir=config.static_dir,
        )

        app = create_app(
            cfg,
            agent_memory=reg.get("vector_memory"),
            agent_registry=reg.get("device_registry"),
            agent_searxng=reg.get("searxng"),
            agent_ntfy=reg.get("ntfy"),
        )

        logger.info(
            f"VTuber 服务启动: http://{config.vtuber_host}:{config.vtuber_port}"
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=config.vtuber_host,
                port=config.vtuber_port,
                log_level="info",
            )
        )
        server.serve()

    except ImportError as e:
        logger.error(f"VTuber 模式缺少依赖: {e}")
    except Exception as e:
        logger.error(f"VTuber 启动失败: {e}")


def run_api(config: AppConfig, reg: ModuleRegistry):
    """API 服务模式"""
    api = reg.get("api")
    if not api:
        logger.error("API 服务不可用 — 请安装: pip install fastapi uvicorn websockets python-multipart")
        return

    logger.info(f"API 服务启动: http://{config.api_host}:{config.api_port}")
    loop = None
    try:
        loop.run_in_executor(
            None, lambda: api.run(host=config.api_host, port=config.api_port)
        )
    except KeyboardInterrupt:
        pass


def run_daemon(config: AppConfig, reg: ModuleRegistry):
    """守护进程模式"""
    daemon = reg.get("daemon")
    if not daemon:
        logger.error("守护进程不可用")
        return

    logger.info("守护进程启动...")
    loop = None
    try:
        loop.run_in_executor(None, daemon.start)
    except KeyboardInterrupt:
        loop.run_in_executor(None, daemon.stop)
        logger.info("守护进程已停止")


def run_status(config: AppConfig, reg: ModuleRegistry):
    """状态查看模式"""
    report = reg.status_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # 设备信息
    device = reg.get("device_registry")
    if device:
        try:
            dev = device.get_device()
            if dev:
                print(f"\n设备: {dev.capabilities.model} (Android {dev.capabilities.android_version})")
        except Exception:
            pass

    # 数据统计
    collector = reg.get("data_collector")
    if collector:
        try:
            stats = collector.stats()
            print(f"\n训练数据: {stats.total_samples} 条, 成功率 {stats.success_rate:.1%}")
            print(f"动作分布: {stats.by_action_type}")
        except Exception:
            pass

    # 进化状态
    tracker = reg.get("metric_tracker")
    if tracker:
        try:
            print(f"\n进化迭代: {tracker.evolution_iterations}")
            print(f"当前模型: {tracker.current_model}")
            print(f"操作成功率: {tracker.overall_success_rate:.1%}")
        except Exception:
            pass


def run_full(config: AppConfig, reg: ModuleRegistry):
    """全功能模式 —— 同时启动 API + Daemon + 进化循环 (sync/threading)"""
    import threading
    
    threads = []
    looper = None  # must stay in scope

    # Daemon
    daemon = reg.get("daemon")
    if daemon:
        threads.append(threading.Thread(target=daemon.start, daemon=True, name="daemon"))

    # API
    api = reg.get("api")
    if api:
        threads.append(threading.Thread(
            target=lambda: api.run(host=config.api_host, port=config.api_port),
            daemon=True, name="api"))

    # 进化循环（后台）
    evolution = reg.get("auto_evolution")
    if evolution:
        threads.append(threading.Thread(
            target=evolution.run_evolution_loop,
            args=(config.evolution_interval,), kwargs={"name": "evolution"},
            daemon=True, name="evolution"))

    if not threads:
        logger.error("无可用服务")
        return

    logger.info(
        f"全功能模式启动 ({len(threads)} 个服务): "
        + ", ".join(t.name for t in threads)
    )

    for t in threads:
        t.start()

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.info("正在关闭...")
        daemon_obj = reg.get("daemon")
        if daemon_obj:
            daemon_obj.stop()
        logger.info("已关闭")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="手机自动化助手 v2.0 - 统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
模式说明:
  explore  自主探索指定应用，生成结构化的探索图谱
  demo     录制人类演示，导出训练数据集
  tune     基于训练数据微调 Ollama 模型
  evolve   启动自主进化循环（自动收集→训练→部署）
  vtuber   启动 VTuber 虚拟形象服务
  api      启动 REST API + WebSocket 服务
  daemon   启动后台守护进程
  full     全功能模式（API + Daemon + 进化）
  status   查看模块状态
        """,
    )

    parser.add_argument("--mode", default="full",
                        choices=["explore", "demo", "tune", "evolve",
                                "vtuber", "api", "daemon", "full", "status"])
    parser.add_argument("--config", default="", help="配置文件路径 (JSON)")

    # ADB
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--device", default="", help="设备序列号")

    # Ollama
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen3.5:2b-q4_K_M")
    parser.add_argument("--vision-model", default="")

    # 探索
    parser.add_argument("--explore-app", default="")
    parser.add_argument("--explore-depth", type=int, default=8)
    parser.add_argument("--explore-nodes", type=int, default=100)
    parser.add_argument("--explore-timeout", type=int, default=300)

    # 演示
    parser.add_argument("--demo-duration", type=int, default=120)
    parser.add_argument("--demo-task", default="")

    # 微调
    parser.add_argument("--tune-dataset", default="")
    parser.add_argument("--tune-model", default="")

    # 进化
    parser.add_argument("--evo-dir", default="./data/evolution")
    parser.add_argument("--evo-interval", type=int, default=30)

    # VTuber
    parser.add_argument("--vt-host", default="0.0.0.0")
    parser.add_argument("--vt-port", type=int, default=8000)
    parser.add_argument("--vt-personality", default="friendly")

    # API
    parser.add_argument("--api-host", default="0.0.0.0")
    parser.add_argument("--api-port", type=int, default=8080)

    # 其他
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--output-dir", default="./output")

    args = parser.parse_args()

    # 构建配置
    if args.config and Path(args.config).exists():
        config = AppConfig.load(args.config)
    else:
        config = AppConfig(
            adb_path=args.adb,
            device_serial=args.device,
            ollama_url=args.ollama_url,
            base_model=args.model,
            vision_model=args.vision_model or args.model,
            explore_app=args.explore_app,
            explore_max_depth=args.explore_depth,
            explore_max_nodes=args.explore_nodes,
            explore_timeout=args.explore_timeout,
            demo_duration=args.demo_duration,
            demo_task=args.demo_task,
            finetune_dataset=args.tune_dataset,
            finetune_model_name=args.tune_model,
            evolution_dir=args.evo_dir,
            evolution_interval=args.evo_interval,
            vtuber_host=args.vt_host,
            vtuber_port=args.vt_port,
            vtuber_personality=args.vt_personality,
            api_host=args.api_host,
            api_port=args.api_port,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
        )

    # 保存配置
    config_dir = Path(config.data_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    config.save(str(config_dir / "assistant_config.json"))

    # 初始化模块
    logger.info("=" * 60)
    logger.info("手机自动化助手 v2.0 正在启动...")
    logger.info(f"模式: {args.mode}")
    logger.info(f"Ollama: {config.ollama_url}")
    logger.info(f"模型: {config.base_model}")
    logger.info("=" * 60)

    reg = init_modules(config)

    # 打印状态
    for name, info in reg.status_report().items():
        if info["status"] != "disabled":
            logger.info(f"  [{name:<15}] {info['status']:<9}")

    # 按模式运行
    mode_handlers = {
        "explore": run_explore,
        "demo": run_demo,
        "tune": run_tune,
        "evolve": run_evolve,
        "vtuber": run_vtuber,
        "api": run_api,
        "daemon": run_daemon,
        "status": run_status,
        "full": run_full,
    }

    handler = mode_handlers.get(args.mode)
    if handler:
        handler(config, reg)
    else:
        logger.error(f"未知模式: {args.mode}")


if __name__ == "__main__":
    try:
        main(())
    except KeyboardInterrupt:
        pass
