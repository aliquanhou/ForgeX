"""Intent Router — 意图分流，决定用户输入走什么处理链路。

意图类型：
  - conversation:    闲聊/问答，直接 LLM 回复，不走工程管道
  - engineering_task:工程任务，走完整 Autonomous Runtime
  - control_command: 控制指令（暂停/恢复等），由 ControlBar 处理
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IntentCategory(str, Enum):
    CONVERSATION = "conversation"
    ENGINEERING_TASK = "engineering_task"
    CONTROL_COMMAND = "control_command"


@dataclass
class IntentRoute:
    category: IntentCategory
    confidence: float
    reason: str


class IntentRouter:
    """Intent Router — 基于关键词/规则快速分类用户意图。

    决定走 Conversation 还是 Engineering 管道。
    """

    # 强工程关键词 — 命中则走 engineering_task
    _ENGINEERING_KEYWORDS = [
        "分析", "重构", "优化", "修复", "实现", "创建", "修改", "删除",
        "编写", "调试", "测试", "部署", "扫描", "检查", "审查", "审计",
        "架构", "设计", "迁移", "升级", "配置",
        "analyze", "refactor", "optimize", "fix", "implement", "create",
        "modify", "delete", "write", "debug", "test", "deploy", "scan",
        "review", "audit", "migrate", "configure",
        "grep", "search", "find", "重构", "报错", "错误", "bug", "crash",
    ]

    # 强闲聊关键词 — 命中则走 conversation
    _CONVERSATION_KEYWORDS = [
        "你好", "嗨", "hello", "hi", "hey", "早上好", "晚上好", "下午好",
        "你是谁", "你能做什么", "介绍一下", "谢谢", "再见",
        "who are you", "what can you do", "thank", "bye",
        "?", "？"  # 纯提问而非指令
    ]

    # 短文本阈值 — 少于 8 个字且无工程关键词 => conversation
    SHORT_TEXT_THRESHOLD = 8

    def route(self, user_input: str) -> IntentRoute:
        """将用户输入路由到正确的处理链路。"""
        text = user_input.strip().lower()

        # 1. 检测工程关键词
        eng_score = sum(1 for kw in self._ENGINEERING_KEYWORDS if kw in text)
        conv_score = sum(1 for kw in self._CONVERSATION_KEYWORDS if kw in text)

        # 2. 短文本且无工程关键词 => conversation
        if len(text) < self.SHORT_TEXT_THRESHOLD and eng_score == 0:
            return IntentRoute(
                category=IntentCategory.CONVERSATION,
                confidence=0.85,
                reason=f"Short input ({len(text)} chars, no engineering keywords)",
            )

        # 3. 工程关键词占优 => engineering_task
        if eng_score > conv_score:
            return IntentRoute(
                category=IntentCategory.ENGINEERING_TASK,
                confidence=min(0.7 + eng_score * 0.1, 0.98),
                reason=f"Engineering keywords detected ({eng_score} matches)",
            )

        # 4. 闲聊关键词占优 => conversation
        if conv_score > eng_score:
            return IntentRoute(
                category=IntentCategory.CONVERSATION,
                confidence=min(0.7 + conv_score * 0.1, 0.95),
                reason=f"Conversation keywords detected ({conv_score} matches)",
            )

        # 5. 默认：无倾向 => conversation（安全选择）
        return IntentRoute(
            category=IntentCategory.CONVERSATION,
            confidence=0.6,
            reason="No strong signal, defaulting to conversation",
        )
