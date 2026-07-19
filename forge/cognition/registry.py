"""Prompt Registry — 模板注册与加载中心。

加载 templates/ 目录下的所有 YAML 模板，缓存并提供查询。
支持按名称、模式、策略类型检索。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _load_yaml(path: Path) -> dict[str, Any]:
    """Simple YAML loader for our structured templates.

    Supports: key: value, key: | (multi-line body).
    Not a full YAML parser — just enough for our template format.
    """
    text = path.read_text(encoding="utf-8")
    result: dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip comments
        if line.strip().startswith('#'):
            i += 1
            continue
        # Multi-line value: key: |
        if ': |' in line:
            key = line.split(':')[0].strip()
            body_lines = []
            i += 1
            while i < len(lines):
                if lines[i].startswith('  '):
                    # Indented content
                    body_lines.append(lines[i].strip())
                elif lines[i].strip() == '':
                    if body_lines and body_lines[-1]:
                        body_lines.append('')
                    i += 1
                    continue
                else:
                    break
                i += 1
            result[key] = '\n'.join(body_lines).rstrip()
            continue
        # Key-value
        if ': ' in line:
            key, val = line.split(': ', 1)
            result[key.strip()] = val.strip().strip('"\'')
        i += 1
    result['_raw'] = text
    return result


class PromptRegistry:
    """Prompt template registry — loads, caches, queries templates."""

    def __init__(self, templates_dir: str | None = None) -> None:
        self._templates_dir = Path(templates_dir or Path(__file__).parent / "templates")
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, name: str) -> dict[str, Any]:
        """Load a template by name, e.g. 'core', 'modes/autonomous'."""
        if name in self._cache:
            return self._cache[name]

        path = self._templates_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {name}")
        data = _load_yaml(path)
        self._cache[name] = data
        return data

    def get_behavior(self, name: str) -> str:
        """Get the 'behavior' section of a template (the actual prompt text)."""
        data = self.load(name)
        return data.get("behavior", data.get("identity", ""))

    def get_mode_behavior(self, mode: str) -> str:
        return self.get_behavior(f"modes/{mode}")

    def get_policy_behavior(self, policy: str) -> str:
        return self.get_behavior(f"policies/{policy}")

    def list_templates(self) -> list[str]:
        templates = sorted(str(p.relative_to(self._templates_dir).with_suffix(''))
                           for p in self._templates_dir.rglob("*.yaml"))
        return templates

    def clear_cache(self) -> None:
        self._cache.clear()
