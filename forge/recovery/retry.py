"""Retry Policy — configurable retry with backoff and strategy.

Different failure modes need different retry strategies:
- Transient errors → exponential backoff
- Logic errors → pivot (different approach)
- Timeouts → increase budget
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


class RetryStrategy(str, Enum):
    IMMEDIATE = "immediate"  # Retry right away
    BACKOFF = "backoff"  # Exponential backoff
    PIVOT = "pivot"  # Try a different approach
    ESCALATE = "escalate"  # Ask for user help


@dataclass
class RetryPolicy:
    """Configuration for retry behavior.

    Usage:
        policy = RetryPolicy(max_retries=3, base_delay=1.0, strategy=RetryStrategy.BACKOFF)
        result = await policy.execute(my_coroutine_fn, arg1, arg2)
    """

    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    strategy: RetryStrategy = RetryStrategy.BACKOFF
    jitter: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for this attempt number."""
        if self.strategy == RetryStrategy.IMMEDIATE:
            return 0.0

        delay = self.base_delay * math.pow(2, attempt - 1)  # exponential
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random
            delay *= 0.5 + random.random() * 0.5  # 50-100% of calculated

        return delay

    async def execute(
        self,
        coro_fn: Callable[..., Awaitable[Any]],
        *args: Any,
        on_retry: Callable[[int, Exception], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a coroutine with retry logic.

        Args:
            coro_fn: Async function to call
            *args: Positional args for coro_fn
            on_retry: Called with (attempt, exception) before each retry
            **kwargs: Keyword args for coro_fn

        Returns:
            Result of coro_fn if successful

        Raises:
            Last exception if all retries exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 2):  # +1 for initial try
            try:
                return await coro_fn(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt > self.max_retries:
                    raise

                if on_retry:
                    on_retry(attempt, e)

                delay = self.get_delay(attempt)
                if delay > 0:
                    await asyncio.sleep(delay)

        # Should not reach here, but safety
        if last_exception:
            raise last_exception
