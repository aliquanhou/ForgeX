"""Prompt Compiler — 运行时将 Runtime 状态编译为最终 System Prompt.

根据 RuntimeState 的当前值（mode、phase、human_override 等），
从 registry 加载对应的模板片段，组合成一条完整的 System Prompt。
"""

from __future__ import annotations

from .registry import PromptRegistry


def _val(v):
    """Safely get value from enum-or-string."""
    return v.value if hasattr(v, 'value') else v


def _phase_label(phase) -> str:
    labels = {
        "init": "初始化", "planning": "规划阶段", "exploration": "分析阶段",
        "implementation": "执行阶段", "verification": "验证阶段",
        "finalizing": "收尾阶段", "completed": "已完成", "failed": "已失败",
        "cancelled": "已取消", "recovery": "恢复中",
    }
    return labels.get(_val(phase), _val(phase))


class PromptCompiler:
    """Prompt Compiler — 运行时编译最终的 System Prompt.

    Usage:
        compiler = PromptCompiler()
        system_prompt = compiler.compile(runtime.state)
        resp = await llm.chat(goal, system=system_prompt)
    """

    def __init__(self, registry: PromptRegistry | None = None) -> None:
        self._registry = registry or PromptRegistry()
        self._version = "forge-agent-v1.0"

    @property
    def version(self) -> str:
        return self._version

    def compile(self, state) -> str:
        """根据 RuntimeState 编译最终的 System Prompt。"""
        parts: list[str] = []

        # 1. 核心人格
        parts.append(self._registry.get_behavior("core"))

        # 2. 模式策略
        mode = _val(getattr(state, 'mode', 'autonomous'))
        try:
            parts.append(self._registry.get_mode_behavior(mode))
        except FileNotFoundError:
            parts.append(self._registry.get_mode_behavior("autonomous"))

        # 3. 当前阶段
        phase = _val(getattr(state, 'phase', 'init'))
        round_n = getattr(state, 'round', 0)
        parts.append(f"当前阶段：{_phase_label(phase)}（第 {round_n} 轮）")

        # 4. 目标
        goal = getattr(state, 'goal', '') or ''
        if goal:
            parts.append(f"用户目标：{goal[:200]}")

        # 5. 人工接管策略
        if getattr(state, 'human_override', False):
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

    def compile_preview(self, state) -> dict:
        return {
            "version": self._version,
            "mode": _val(getattr(state, 'mode', 'autonomous')),
            "phase": _val(getattr(state, 'phase', 'init')),
            "round": getattr(state, 'round', 0),
            "human_override": getattr(state, 'human_override', False),
            "goal": (getattr(state, 'goal', '') or '')[:100],
        }
