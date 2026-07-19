"""Example: A simple ForgeX plugin that adds a custom verifier hook.

This demonstrates the Plugin SDK contract.
Real plugins would go in plugins/ directory, not forge/plugin/examples/.
"""

from forge.plugin import ForgePlugin, PluginSpec, PluginCapability, PluginHook


class ExampleVerifierPlugin(ForgePlugin):
    """Example plugin that adds an additional verification step."""

    spec = PluginSpec(
        name="example-verifier",
        version="1.0.0",
        description="Example plugin — adds custom verification",
        capabilities=[PluginCapability.HOOKS, PluginCapability.VERIFIER],
    )

    async def initialize(self, runtime):
        """Register hooks."""
        print(f"  [plugin] {self.name} v{self.version} initialized")

    async def hooks(self):
        async def after_tool_hook(tool_name: str, result):
            if tool_name in ("write_file", "edit_file"):
                print(f"  [plugin:example] Tool {tool_name} completed")
            return result

        return {
            PluginHook.AFTER_TOOL: [after_tool_hook],
        }
