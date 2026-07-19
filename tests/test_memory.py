"""Tests for memory/state compression module."""


class TestStateCompressor:
    """State compression for LLM context."""

    def test_compress_empty_state(self):
        from forge.kernel.state import RuntimeState
        from forge.memory.compressor import StateCompressor

        state = RuntimeState()
        state.goal = "test goal"

        compressor = StateCompressor()
        compressed = compressor.compress(state)

        assert compressed.goal == "test goal"
        assert compressed.to_prompt()
        assert compressed.token_estimate() > 0

    def test_compress_with_data(self):
        from forge.kernel.state import RuntimeState
        from forge.memory.compressor import StateCompressor

        state = RuntimeState()
        state.goal = "implement login feature"
        state.add_fact("User model exists in models/user.py")
        state.add_fact("Auth router exists in routes/auth.py")
        state.open_questions = ["Where is the password hashing?"]
        state.critical_files = ["models/user.py", "routes/auth.py"]

        compressor = StateCompressor()
        compressed = compressor.compress(state)

        prompt = compressed.to_prompt()
        assert "implement login feature" in prompt
        assert "User model" in prompt
        assert "Where is" in prompt
        assert "models/user.py" in prompt

    def test_compression_budget(self):
        from forge.kernel.state import RuntimeState
        from forge.memory.compressor import StateCompressor

        state = RuntimeState()
        state.goal = "x" * 1000
        for i in range(50):
            state.add_fact(f"fact_{i}: " + "x" * 100)
        for i in range(20):
            state.critical_files.append(f"file_{i}.py")

        compressor = StateCompressor(max_tokens=200)
        compressed = compressor.compress(state)

        assert compressed.token_estimate() <= 300
