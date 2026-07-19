"""Tests for Decision Engine v2 — LLM Judge + Uncertainty Entropy."""


class TestDecisionEngineV2:
    """Decision Engine with LLM Judge fallback."""

    def test_stop_conditions(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="completed", round=0, goal="t", intent="t")
        d = engine._rule_decide(ctx)
        assert d.kind == DecisionKind.STOP

    def test_recover_on_error(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="impl", round=3, goal="t", intent="t",
                              error_count=1, last_error="disk full")
        d = engine._rule_decide(ctx)
        assert d.kind == DecisionKind.RECOVER

    def test_uncertainty_triggers_explore(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="implementation", round=3, goal="t", intent="t",
                              uncertainty_entropy=0.8, knowledge_coverage=0.2)
        d = engine._rule_decide(ctx)
        assert d.kind == DecisionKind.CONTINUE_EXPLORE

    def test_low_knowledge_triggers_explore(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="implementation", round=3, goal="t", intent="t",
                              knowledge_coverage=0.1)
        d = engine._rule_decide(ctx)
        assert d.kind == DecisionKind.CONTINUE_EXPLORE

    def test_evi_pivot(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="exploration", round=5, goal="t", intent="t",
                              last_evi_score=0.1, low_evi_streak=3)
        d = engine._rule_decide(ctx)
        assert d.kind == DecisionKind.WRITE_CODE

    def test_high_confidence_write(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="implementation", round=4, goal="t", intent="t",
                              last_evi_score=0.8,
                              knowledge_coverage=0.8, uncertainty_entropy=0.1)
        d = engine._rule_decide(ctx)
        assert d.kind == DecisionKind.WRITE_CODE
        assert d.is_certain


class TestUncertaintyHelpers:
    """Uncertainty entropy and knowledge coverage."""

    def test_compute_entropy(self):
        from forge.decision.engine import compute_uncertainty_entropy

        entropy = compute_uncertainty_entropy(
            open_questions=5,
            critical_files_known=0,
            evi_trend=[0.1, 0.1, 0.1],
            low_evi_streak=5,
        )
        assert entropy > 0.5  # High uncertainty

        entropy2 = compute_uncertainty_entropy(
            open_questions=0,
            critical_files_known=5,
            evi_trend=[0.9, 0.8, 0.9],
            low_evi_streak=0,
        )
        assert entropy2 < 0.5  # Low uncertainty

    def test_knowledge_coverage(self):
        from forge.decision.engine import compute_knowledge_coverage

        cov = compute_knowledge_coverage(
            confirmed_facts=0,
            open_questions=5,
            critical_files_known=0,
        )
        assert cov < 0.3

        cov2 = compute_knowledge_coverage(
            confirmed_facts=10,
            open_questions=0,
            critical_files_known=5,
        )
        assert cov2 > 0.5
