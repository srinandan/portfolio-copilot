"""Runtime guardrails wired into the ADK Runner (ADR-0026)."""

from .model_armor_plugin import (
    MODEL_ARMOR_BLOCKED_METADATA_KEY,
    build_model_armor_plugin,
    guardrail_block_frame,
    wire_is_model_armor_block,
)

__all__ = [
    "MODEL_ARMOR_BLOCKED_METADATA_KEY",
    "build_model_armor_plugin",
    "guardrail_block_frame",
    "wire_is_model_armor_block",
]
