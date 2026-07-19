"""Tests for Decision Engine."""


class TestDecisionEngine:
    """Decision Engine — the intelligence layer."""

    def test_stop_on_terminal_phase(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="completed", round=0, goal="test", intent="test")
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.STOP
        assert d.confidence == 1.0

    def test_finalize_when_no_budget(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="implementation", round=50, goal="test", intent="test", rounds_remaining=0)
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.FINALIZE
        assert d.confidence >= 0.8

    def test_recover_on_error(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="implementation", round=3, goal="test", intent="test",
                              error_count=1, last_error="disk full")
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.RECOVER

    def test_ask_user_on_critical_errors(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="implementation", round=3, goal="test", intent="test",
                              error_count=3, last_error="critical failure")
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.ASK_USER

    def test_pivot_on_low_evi_explore(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="exploration", round=5, goal="test", intent="test",
                              last_evi_score=0.1, low_evi_streak=3)
        d = engine.decide(ctx)
        # Should pivot to WRITE_CODE instead of continuing exploration
        assert d.kind == DecisionKind.WRITE_CODE

    def test_rollback_on_low_evi_implement(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="implementation", round=5, goal="test", intent="test",
                              last_evi_score=0.1, low_evi_streak=3)
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.ROLLBACK

    def test_decide_explore_with_knowledge(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="exploration", round=2, goal="test", intent="test",
                              open_questions=0, confirmed_facts=3)
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.WRITE_CODE
        assert d.confidence >= 0.8

    def test_decide_explore_needs_more(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="exploration", round=2, goal="test", intent="test",
                              open_questions=2, confirmed_facts=1, critical_files_known=1)
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.SEARCH_SYMBOL or d.kind == DecisionKind.DEEP_READ or d.kind == DecisionKind.CONTINUE_EXPLORE

    def test_verify_after_modification(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="verification", round=4, goal="test", intent="test",
                              last_evi_tool="write_file")
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.VERIFY_FILE

    def test_finalize_when_all_phases_done(self):
        from forge.decision import DecisionEngine, DecisionContext, DecisionKind

        engine = DecisionEngine()
        ctx = DecisionContext(phase="verification", round=5, goal="test", intent="test",
                              phases_completed=4, phases_total=5)
        d = engine.decide(ctx)
        assert d.kind == DecisionKind.FINALIZE

    def test_decision_properties(self):
        from forge.decision import Decision, DecisionKind

        certain = Decision(kind=DecisionKind.STOP, confidence=0.95, reason="done")
        assert certain.is_certain
        assert not certain.is_uncertain

        uncertain = Decision(kind=DecisionKind.CONTINUE_EXPLORE, confidence=0.3, reason="unsure")
        assert uncertain.is_uncertain
        assert not uncertain.is_certain
