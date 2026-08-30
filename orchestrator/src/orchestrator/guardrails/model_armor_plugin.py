"""Model Armor runtime guardrail plugin wiring (ADR-0026).

This complements the project-level Model Armor *floor settings*
(ADR-0025, ``scripts/model_armor_floor_settings.py``) with an in-runtime,
*per-request* guardrail. ADK's :class:`ModelArmorPlugin` screens each user
turn and model response against regional Model Armor *templates* via the
ordinary ``before_model_callback`` / ``after_model_callback`` seams, so a
prompt-injection / RAI / SDP / malicious-URI hit is blocked inside the Runner
rather than only at the project floor.

Two layers, one config source:

* **Floor settings** — always-on project backstop (``global``), configured
  out of band by ``scripts/model_armor_floor_settings.py``.
* **This plugin** — per-request layer on the sensitive planning path, wired
  onto the Runner. Needs regional Model Armor *template* resources, created by
  ``scripts/setup_model_armor_templates.py``.

Default ON. :func:`build_model_armor_plugin` builds the plugin whenever at least
one template is configured, *unless* ``MODEL_ARMOR_PLUGIN_ENABLED`` is explicitly
false. A deploy with no template configured is still inert (returns ``None``),
so the guardrail activates automatically once the templates exist without an
operator having to flip a separate enable flag. On a match the plugin blocks the
turn (detection → block); there is no redaction/de-identify path.

Block signalling. A block surfaces as an ``LlmResponse`` carrying
``custom_metadata={"model_armor_blocked": True}``; the streaming layer
(``server._drain_runner``) turns that into an advisory ``guardrail_block`` SSE
frame plus a WARNING log. That is deliberately the *advisory* channel, mirroring
``progress.py`` — the immutable governance audit log is untouched. Promoting a
guardrail block to a first-class ``GUARDRAIL_BLOCKED`` audit ``EventType``
(spanning the Python + Go audit contracts) is a tracked follow-up, not part of
this wiring.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, Optional

from ..logger import get_logger

if TYPE_CHECKING:
    from google.adk.plugins.base_plugin import BasePlugin

logger = get_logger(__name__)

# Key the ADK ModelArmorPlugin stamps on a blocked LlmResponse's custom_metadata.
# Must match google.adk.integrations.model_armor._plugin._blocked_response.
MODEL_ARMOR_BLOCKED_METADATA_KEY = "model_armor_blocked"

# Environment configuration -------------------------------------------------
ENABLED_ENV = "MODEL_ARMOR_PLUGIN_ENABLED"
# Full template resource names take precedence when set:
#   projects/{project}/locations/{location}/templates/{template}
PROMPT_TEMPLATE_ENV = "MODEL_ARMOR_PROMPT_TEMPLATE"
RESPONSE_TEMPLATE_ENV = "MODEL_ARMOR_RESPONSE_TEMPLATE"
# ...otherwise a full name is assembled from project + location + template id.
LOCATION_ENV = "MODEL_ARMOR_LOCATION"
PROMPT_TEMPLATE_ID_ENV = "MODEL_ARMOR_PROMPT_TEMPLATE_ID"
RESPONSE_TEMPLATE_ID_ENV = "MODEL_ARMOR_RESPONSE_TEMPLATE_ID"
BLOCK_ON_FAILURE_ENV = "MODEL_ARMOR_BLOCK_ON_SCREENING_FAILURE"
INPUT_BLOCKED_MESSAGE_ENV = "MODEL_ARMOR_INPUT_BLOCKED_MESSAGE"
OUTPUT_BLOCKED_MESSAGE_ENV = "MODEL_ARMOR_OUTPUT_BLOCKED_MESSAGE"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _project() -> Optional[str]:
    return os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")


def _resolve_template(full_env: str, id_env: str) -> Optional[str]:
    """Resolves a Model Armor template resource name from env.

    Prefers a fully-qualified name in ``full_env``; otherwise assembles one
    from project + ``MODEL_ARMOR_LOCATION`` + the template id in ``id_env``.
    Returns ``None`` when neither is configured.
    """
    full = os.environ.get(full_env)
    if full:
        return full.strip()

    template_id = os.environ.get(id_env)
    if not template_id:
        return None

    project = _project()
    location = os.environ.get(LOCATION_ENV)
    if not project or not location:
        logger.warning(
            "%s set but %s/%s missing; cannot assemble a template resource name.",
            id_env,
            "GOOGLE_CLOUD_PROJECT/PROJECT_ID" if not project else "",
            LOCATION_ENV if not location else "",
        )
        return None
    return f"projects/{project}/locations/{location}/templates/{template_id.strip()}"


def build_model_armor_plugin() -> Optional["BasePlugin"]:
    """Builds the Model Armor guardrail plugin from environment configuration.

    Returns ``None`` (Runner runs without the plugin) when the plugin is
    disabled or no template is configured. Never raises — a misconfiguration
    degrades to "no runtime guardrail" and is logged, so the floor-settings
    backstop still applies and the server still starts.
    """
    if not _env_bool(ENABLED_ENV, default=True):
        logger.info("Model Armor runtime plugin explicitly disabled (%s is false).", ENABLED_ENV)
        return None

    prompt_template = _resolve_template(PROMPT_TEMPLATE_ENV, PROMPT_TEMPLATE_ID_ENV)
    response_template = _resolve_template(RESPONSE_TEMPLATE_ENV, RESPONSE_TEMPLATE_ID_ENV)

    if not prompt_template and not response_template:
        logger.info(
            "Model Armor runtime plugin is enabled by default but no template is configured "
            "(set %s / %s or the *_TEMPLATE_ID + %s convenience vars); "
            "running without the runtime guardrail until templates are provisioned.",
            PROMPT_TEMPLATE_ENV,
            RESPONSE_TEMPLATE_ENV,
            LOCATION_ENV,
        )
        return None

    try:
        from google.adk.integrations.model_armor import (
            ModelArmorConfig,
            ModelArmorPlugin,
        )
    except ImportError:
        logger.exception(
            "Model Armor plugin requested but google-cloud-modelarmor is not "
            "installed; running without the runtime guardrail."
        )
        return None

    config_kwargs: Dict[str, Any] = {
        "prompt_template_name": prompt_template,
        "response_template_name": response_template,
        "block_on_screening_failure": _env_bool(BLOCK_ON_FAILURE_ENV, default=True),
    }
    input_msg = os.environ.get(INPUT_BLOCKED_MESSAGE_ENV)
    if input_msg:
        config_kwargs["input_blocked_message"] = input_msg
    output_msg = os.environ.get(OUTPUT_BLOCKED_MESSAGE_ENV)
    if output_msg:
        config_kwargs["output_blocked_message"] = output_msg

    try:
        config = ModelArmorConfig(**config_kwargs)
        plugin = ModelArmorPlugin(config=config)
    except Exception:
        logger.exception("Failed to construct Model Armor plugin; running without the runtime guardrail.")
        return None

    logger.info(
        "Model Armor runtime guardrail enabled (prompt_template=%s response_template=%s block_on_failure=%s).",
        prompt_template or "<none>",
        response_template or "<none>",
        config_kwargs["block_on_screening_failure"],
    )
    return plugin


def wire_is_model_armor_block(wire: Dict[str, Any]) -> bool:
    """True when a serialized event wire dict is a Model Armor block.

    Detects the ``custom_metadata`` flag the plugin stamps on the safe
    replacement response, from the JSON-mode ``model_dump`` produced by
    ``server._event_to_wire``.
    """
    if not isinstance(wire, dict):
        return False
    metadata = wire.get("custom_metadata")
    if not isinstance(metadata, dict):
        return False
    return bool(metadata.get(MODEL_ARMOR_BLOCKED_METADATA_KEY))


def guardrail_block_frame(wire: Dict[str, Any]) -> Dict[str, Any]:
    """Builds the advisory ``guardrail_block`` SSE frame for a detected block.

    Advisory only, on the same channel as ``progress.py`` frames — it tells the
    UI a turn was blocked so it can render a notice; it carries no governance
    weight and never gates execution.
    """
    frame: Dict[str, Any] = {
        "kind": "guardrail_block",
        "source": "model_armor",
    }
    author = wire.get("author") if isinstance(wire, dict) else None
    if author:
        frame["author"] = author
    return frame
