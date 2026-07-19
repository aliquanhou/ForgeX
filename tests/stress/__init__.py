"""Stress tests for ForgeX v0.5 LTS kernel validation."""


async def _noop(state=None):
    """No-op async handler for runtime phases."""
    pass


async def _noop_add_fact(state):
    """Add a noop fact."""
    state.add_fact("noop")
