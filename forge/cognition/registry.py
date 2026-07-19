"""Prompt Registry — 模板注册与加载中心。

加载 `templates/` 目录下的所有 YAML 模板，缓存并提供查询。
支持按名称、模式、策略类型检索。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _load_yaml_text(path: Path) -> dict[str, Any]:
    """Load a YAML-ish template file and parse frontmatter + body."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---") if text.startswith("---") else [""]
    raw = parts[-1].strip() if len(parts) > 1 else text.strip()

    result: dict[str, Any] = {}
    for line in raw.splitlines():
        if ": " in line and not line.startswith(" "):
            k, v = line.split(": ", 1)
            result[k.strip()] = v.strip().strip('"')
        elif "|" in line:
            key = line.split(":")[0].strip()
            body_start = raw.index(line) + len(line)
            body = raw[body_start:].strip()
            result[key] = body
            break
    result["_raw"] = raw
    return result


class PromptRegistry:
    """Prompt template registry — loads, caches, queries templates."""

    def __init__(self, templates_dir: str | None = None) -> None:
        self._templates_dir = Path(templates_dir or Path(__file__).parent / "templates")
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, name: str) -> dict[str, Any]:
        """Load a template by path relative to templates_dir, e.g. 'core', 'modes/autonomous'."""
        if name in self._cache:
            return self._cache[name]

        path = self._templates_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {name} ({path})")

        data = _load_yaml_text(path)
        self._cache[name] = data
        return data

    def get_behavior(self, name: str) -> str:
        """Get the 'behavior' section of a template (the actual prompt text)."""
        data = self.load(name)
        return data.get("behavior", data.get("_raw", ""))

    def get_identity(self) -> str:
        """Get core identity prompt."""
        return self.get_behavior("core")

    def get_mode_behavior(self, mode: str) -> str:
        """Get behavior for a specific RuntimeMode."""
        return self.get_behavior(f"modes/{mode}")

    def get_policy_behavior(self, policy: str) -> str:
        """Get behavior for a specific policy."""
        return self.get_behavior(f"policies/{policy}")

    def list_templates(self) -> list[str]:
        """List all available templates."""
        templates: list[str] = []
        for yaml_file in self._templates_dir.rglob("*.yaml"):
            rel = yaml_file.relative_to(self._templates_dir)
            templates.append(str(rel.with_suffix("")))
        return sorted(templates)

    def clear_cache(self) -> None:
        self._cache.clear()
