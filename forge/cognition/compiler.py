"""Prompt Compiler — 运行时将 Runtime 状态编译为最终 System Prompt.

根据 RuntimeState 的当前值（mode、phase、human_override 等），
从 registry 加载对应的模板片段，组合成一条完整的 System Prompt。

Future: 可以扩展为支持 World Model Summary、安全策略、用户偏好等动态注入。
"""

from __future__ import annotations

from forge.kernel.state import RuntimeState, RuntimeMode

from .registry import PromptRegistry


def _phase_label(phase: str) -> str:
    labels = {
        "init": "初始化",
        "planning": "规划阶段",
        "exploration": "分析阶段",
        "implementation": "执行阶段",
        "verification": "验证阶段",
        "finalizing": "收尾阶段",
        "completed": "已完成",
        "failed": "已失败",
        "cancelled": "已取消",
    }
    return labels.get(phase, phase)


class PromptCompiler:
    """Prompt Compiler — 运行时编译最终的 System Prompt.

    Usage:
        compiler = PromptCompiler()
        system_prompt = compiler.compile(runtime.state)
        resp = await llm.chat(goal, system=system_prompt)
    """

    def __init__(self, registry: PromptRegistry | None = None) -> None:
        self._registry = registry or PromptRegistry()
        self._version: str = "forge-agent-v1.0"

    @property
    def version(self) -> str:
        return self._version

    def compile(self, state: RuntimeState) -> str:
        """根据 RuntimeState 编译最终的 System Prompt。"""
        parts: list[str] = []

        # 1. 核心人格（不变）
        parts.append(self._registry.get_identity())

        # 2. 模式策略（按 RuntimeMode 切换）
        try:
            parts.append(self._registry.get_mode_behavior(state.mode.value))
        except FileNotFoundError:
            parts.append(self._registry.get_mode_behavior("autonomous"))

        # 3. 当前阶段上下文
        parts.append(f"当前阶段：{_phase_label(state.phase.value)}（第 {state.round} 轮）")

        # 4. 目标
        if state.goal:
            parts.append(f"用户目标：{state.goal[:200]}")

        # 5. 人工接管策略
        if state.human_override:
            try:
                parts.append(self._registry.get_policy_behavior("human_override"))
            except FileNotFoundError:
                pass

        # 6. 回滚策略
        try:
            parts.append(self._registry.get_policy_behavior("rollback"))
        except FileNotFoundError:
            pass

        return "\n\n".join(parts)

    def compile_preview(self, state: RuntimeState) -> dict:
        """返回编译预览（用于 Inspector 显示）。"""
        return {
            "version": self._version,
            "mode": state.mode.value,
            "phase": state.phase.value,
            "round": state.round,
            "human_override": state.human_override,
            "goal": state.goal[:100] if state.goal else "",
        }
