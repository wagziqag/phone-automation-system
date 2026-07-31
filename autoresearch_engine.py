#!/usr/bin/env python3
"""
AutoresearchEngine — 9 阶段自我迭代研究管道。

供 main.py 统一编排器使用。
"""

import logging
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger("autoresearch")


class AutoresearchEngine:
    """
    9 阶段自主研究管道：

    1. 工具调用 → 2. 规划 → 3. 推理 → 4. 检索 → 5. 执行
    → 6. 反思 → 7. 验证 → 8. 进化 → 9. 模板化
    """

    def __init__(
        self,
        run_fn: Callable[[str], Dict[str, Any]],
        experience_retriever=None,
        fine_tune_trigger=None,
        template_manager=None,
        max_iterations: int = 3,
    ):
        """
        Args:
            run_fn: 执行函数，签名为 (task_description) → {"success": bool, "steps": [...], ...}
            experience_retriever: 经验检索器
            fine_tune_trigger: 微调触发器
            template_manager: 模板管理器
            max_iterations: 最大迭代次数
        """
        self.run = run_fn
        self.retriever = experience_retriever
        self.tuner = fine_tune_trigger
        self.templates = template_manager
        self.max_iterations = max_iterations

    def execute(self, complex_task: str) -> Dict[str, Any]:
        """运行 9 阶段自主研究管道。"""
        logger.info(f"[autoresearch] 开始: {complex_task}, 最多 {self.max_iterations} 轮")

        research_log: List[Dict] = []
        best_success_rate = 0.0
        best_description = complex_task

        for iteration in range(self.max_iterations):
            logger.info(f"[autoresearch] 第 {iteration + 1}/{self.max_iterations} 轮")

            # 1. 工具调用 & 5. 执行
            result = self.run(best_description)

            if not result.get("success"):
                # 2. 规划 & 3. 推理
                failure_analysis = self._analyze(result)
                improved = self._improve(best_description, failure_analysis, result)

                # 4. 检索
                related = self.retriever.retrieve(improved) if self.retriever else []

                research_log.append({
                    "iteration": iteration + 1,
                    "description": best_description,
                    "result": result,
                    "failure_analysis": failure_analysis,
                    "improved_description": improved,
                    "related_experience": related,
                })

                best_description = improved

                # 6. 反思 & 7. 验证
                sr = self._calc_success_rate(research_log)
                if sr > best_success_rate:
                    best_success_rate = sr
                if sr >= 0.8:
                    logger.info(f"[autoresearch] 达到目标成功率 {sr}")
                    break
            else:
                research_log.append({
                    "iteration": iteration + 1,
                    "description": best_description,
                    "result": result,
                    "success": True,
                })
                sr = self._calc_success_rate(research_log)
                if sr >= 0.9:
                    logger.info(f"[autoresearch] 高成功率 {sr}，提前结束")
                    break

        final_rate = self._calc_success_rate(research_log)

        # 8. 进化
        if final_rate < 0.5 and len(research_log) >= 3 and self.tuner:
            logger.info("[autoresearch] 触发模型微调")
            self.tuner.force_trigger()

        # 9. 模板化
        template_created = False
        if final_rate >= 0.7 and self.templates:
            best_steps = self._extract_best_steps(research_log)
            if best_steps:
                self.templates.save_research_template(complex_task, best_description, best_steps)
                template_created = True

        return {
            "complex_task": complex_task,
            "iterations": self.max_iterations,
            "actual_iterations": len(research_log),
            "final_success_rate": final_rate,
            "best_description": best_description,
            "research_log": research_log,
            "template_created": template_created,
        }

    def _analyze(self, result: Dict[str, Any]) -> str:
        """分析失败原因。"""
        if result.get("success"):
            return "任务成功，无需分析"

        failed_step = result.get("failed_step")
        execution_log = result.get("execution_log", [])

        if failed_step and execution_log:
            for log in execution_log:
                if log.get("step") == failed_step:
                    error = log.get("error", "")
                    action = log.get("action", "")
                    return f"步骤 '{action}' 失败: {error}"

        return f"未知失败: {result.get('error', '无错误信息')}"

    def _improve(self, description: str, failure: str,
                 result: Dict[str, Any]) -> str:
        """改进任务描述。"""
        lines = [description]

        if "找不到" in failure:
            lines.append("请使用更具体的元素描述")
        if "超时" in failure:
            lines.append("请分解为更小的步骤")
        if "权限" in failure:
            lines.append("请先检查权限配置")
        if "连接" in failure:
            lines.append("请先确认设备连接状态")

        if len(lines) == 1:
            lines.append("请尝试替代方案")

        return "。".join(lines)

    def _calc_success_rate(self, log: List[Dict]) -> float:
        if not log:
            return 0.0
        successes = sum(1 for entry in log if entry.get("success") or entry.get("result", {}).get("success"))
        return successes / len(log)

    def _extract_best_steps(self, log: List[Dict]) -> List[Dict]:
        for entry in reversed(log):
            if entry.get("success") or entry.get("result", {}).get("success"):
                return entry.get("result", {}).get("steps", [])
        return []