"""ForgeX Cognition Layer — Prompt Runtime (FPR).

第六层架构：Runtime → World Model → Decision → Tool → Studio → **Cognition**。

负责根据 Runtime 状态动态编译 System Prompt，替代散落在 handler 中的硬编码字符串。

Usage:
    from forge.cognition import prompt_compiler
    prompt = prompt_compiler.compile(runtime.state)
    resp = await llm.chat(goal, system=prompt)
"""

from .compiler import PromptCompiler
from .registry import PromptRegistry

# 单例
_registry = PromptRegistry()
prompt_compiler = PromptCompiler(_registry)

__all__ = [
    "PromptCompiler",
    "PromptRegistry",
    "prompt_compiler",
]
