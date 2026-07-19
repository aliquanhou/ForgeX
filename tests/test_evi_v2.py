"""Tests for EVI Engine v2 (new formula)."""


class TestEVIEngineV2:
    """EVI v2: EVI = ΔInfo + ΔProgress + ΔRiskReduction - α·Cost"""

    def test_high_value_read(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate(
            "read_file",
            {"path": "file.py"},
            {"content": "def foo():\n    pass\n" * 10, "total_lines": 20},
            [],
        )
        assert result.score > 0.3
        assert not result.low_value
        assert result.cost_effective

    def test_low_value_empty_read(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate(
            "read_file",
            {"path": "empty.py"},
            {"content": "", "total_lines": 0},
            [],
        )
        assert result.score < 0.2
        assert result.low_value

    def test_large_read_diminishing_returns(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        # 5000 lines — cost should outweigh info gain
        big_content = "\n".join(f"line {i}" for i in range(5000))
        result = evi.evaluate(
            "read_file",
            {"path": "big.py"},
            {"content": big_content, "total_lines": 5000},
            [],
        )
        # Large read should have significant cost penalty
        assert result.cost > 0.2
        # info_gain should be limited by diminishing returns
        assert result.info_gain < 0.5

    def test_precise_grep_high_value(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate(
            "grep",
            {"pattern": "class Factory"},
            {"matches": ["src/factory.py:10:class Factory:"], "count": 1},
            [],
        )
        assert result.score > 0.5
        assert result.high_value

    def test_noisy_grep_lower_value(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate(
            "grep",
            {"pattern": "print"},
            {"matches": [f"file{i}.py:1:print()" for i in range(100)], "count": 100},
            [],
        )
        # 100 matches = noise, should not be high value
        assert not result.high_value

    def test_write_file_progress(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate(
            "write_file",
            {"path": "new.py", "content": "x = 1"},
            {"bytes": 5},
            [],
        )
        # Write should show high progress but low info gain
        assert result.progress > 0.5
        assert result.info_gain < 0.4

    def test_error_has_info_value(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate("execute", {"command": "python bad.py"},
                               {"error": "ModuleNotFoundError: No module named 'nonexistent'", "exit_code": 1},
                               [])
        assert result.info_gain >= 0.5  # Errors are informative

    def test_cost_effective_detection(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        # High info, low cost
        result = evi.evaluate("grep", {"pattern": "class"},
                               {"matches": ["a.py:1:class X:"], "count": 1}, [])
        assert result.cost_effective

    def test_cost_ineffective_detection(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        # Large read of irrelevant file — high cost, low info
        big_content = "\n".join(f"# comment {i}" for i in range(2000))
        result = evi.evaluate("read_file", {"path": "huge.log"},
                               {"content": big_content, "total_lines": 2000}, [])
        # cost should be significant
        assert result.cost > 0.1

    def test_low_value_streak(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        for _ in range(3):
            evi.evaluate("read_file", {"path": "empty.py"}, {"content": "", "total_lines": 0}, [])
        assert evi.low_value_streak >= 3
        assert evi.should_force_finalize

    def test_breakdown_fields(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate("read_file", {"path": "f.py"},
                               {"content": "code", "total_lines": 5}, [])
        assert "info_gain" in result.breakdown
        assert "cost" in result.breakdown
        assert "cost_effective" in result.breakdown
        assert "benefit" in result.breakdown
        assert "raw_score" in result.breakdown
