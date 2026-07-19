"""Configuration for Forge Agent OS."""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class ForgeConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Project ---
    workspace_root: Path = Path.home() / "forge_workspace"
    data_dir: Path = Path.home() / ".forge"

    # --- LLM ---
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"  # V3.1
    llm_reasoning_model: str = "deepseek-reasoner"  # R1
    llm_verifier_model: str = "deepseek-chat"  # fallback small model
    llm_temperature: float = 0.1
    llm_max_tokens: int = 8192
    llm_request_timeout: float = 120.0

    # --- Runtime ---
    runtime_max_rounds: int = 50
    runtime_token_budget: int = 100_000
    runtime_state_max_tokens: int = 500  # compressed state size

    # --- EVI ---
    evi_low_gain_threshold: float = 0.15
    evi_force_finalize_rounds: int = 3

    # --- Sandbox ---
    sandbox_type: str = "subprocess"  # subprocess | docker
    sandbox_timeout: float = 30.0
    sandbox_max_output: int = 10_000_000

    # --- Storage ---
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://localhost:5432/forge"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["*"]


config = ForgeConfig()
