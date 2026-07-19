"""Stress 9: Cost tracking — verify token budgets are accurately tracked."""


class TestCostTracking:
    """Verify budget and cost tracking accuracy."""

    def test_budget_tokens_tracked(self):
        from forge.kernel.budget import BudgetManager, BudgetKind

        b = BudgetManager(token_limit=10000)
        b.consume_tokens(500)
        b.consume_tokens(1500)

        state = b.get_state(BudgetKind.TOKENS)
        assert state.used == 2000
        assert state.remaining == 8000
        assert state.pct == 0.2

    def test_budget_exhaustion(self):
        from forge.kernel.budget import BudgetManager

        b = BudgetManager(token_limit=100, round_limit=100)
        b.consume_tokens(95)
        assert not b.is_exhausted

        b.consume_tokens(10)
        assert b.is_exhausted

    def test_budget_multiple_dimensions(self):
        from forge.kernel.budget import BudgetManager, BudgetKind

        b = BudgetManager(token_limit=500, round_limit=3, read_limit=10)

        b.consume_tokens(100)
        b.consume_round()
        b.consume_read()

        s = b.summary
        assert s["tokens"]["used"] == 100
        assert s["rounds"]["used"] == 1
        assert s["reads"]["used"] == 1

    def test_warning_triggers_at_threshold(self):
        from forge.kernel.budget import BudgetManager

        b = BudgetManager(token_limit=100, round_limit=100)
        b.consume_tokens(90)
        warnings = b.check_warnings()
        assert len(warnings) > 0
        assert any("token" in w.lower() for w in warnings)
