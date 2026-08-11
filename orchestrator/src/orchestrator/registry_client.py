"""Agent Registry REST client."""

import io
import os
import ssl
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Any

import httpx
from google.auth import default as google_auth_default
from google.auth.transport import mtls
from google.auth.transport.requests import Request as GoogleAuthRequest

from .logger import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://agentregistry.googleapis.com/v1alpha"
DEFAULT_MTLS_BASE_URL = "https://agentregistry.mtls.googleapis.com/v1alpha"


@dataclass
class Skill:
    name: str
    target_state: str = ""
    default_revision: str = ""


class GoogleAuth(httpx.Auth):
    """httpx Auth flow using Google credentials."""

    def __init__(self, credentials: Any, quota_project_id: str | None = None):
        self.credentials = credentials
        self.quota_project_id = quota_project_id
        self._auth_request = GoogleAuthRequest()

    def auth_flow(self, request: httpx.Request):
        if hasattr(self.credentials, "before_request"):
            self.credentials.before_request(self._auth_request, request.method, str(request.url), request.headers)
        else:
            if not self.credentials.valid:
                try:
                    self.credentials.refresh(self._auth_request)
                except Exception:
                    logger.exception("Credential refresh in auth_flow failed")
            token = getattr(self.credentials, "token", None)
            if token and isinstance(token, str):
                request.headers["Authorization"] = f"Bearer {token}"
            elif hasattr(self.credentials, "apply"):
                self.credentials.apply(request.headers)

        quota_project = getattr(self.credentials, "quota_project_id", None) or self.quota_project_id
        if quota_project and "x-goog-user-project" not in request.headers:
            request.headers["x-goog-user-project"] = quota_project

        yield request


def _create_mtls_ssl_context() -> ssl.SSLContext | None:
    """Creates an SSLContext with client certificates loaded from default mTLS source."""
    if not mtls.has_default_client_cert_source():
        return None
    source = mtls.default_client_cert_source()
    if not source:
        return None
    try:
        cert_bytes, key_bytes = source()
        if not cert_bytes or not key_bytes:
            return None
        ssl_context = ssl.create_default_context()
        with tempfile.NamedTemporaryFile(delete=False) as c_file, tempfile.NamedTemporaryFile(delete=False) as k_file:
            c_file.write(cert_bytes)
            k_file.write(key_bytes)
            c_file.flush()
            k_file.flush()
            ssl_context.load_cert_chain(certfile=c_file.name, keyfile=k_file.name)
            os.unlink(c_file.name)
            os.unlink(k_file.name)
        return ssl_context
    except Exception as e:
        logger.debug(f"Failed to load mTLS client certificate: {e}")
        return None


_STRIP_SECTIONS_STARTING_WITH = (
    "## Acceptance criteria",
    "## Acceptance Criteria",
    "## Registry metadata",
    "## Registry Metadata",
    "## When this skill runs",
    "## When This Skill Runs",
    "## Drafting logic",  # action-drafting; obsolete after PR #259
    "## Pre-check, before drafting",  # action-drafting; deterministic path
    "## Deterministic calculations",  # spending-analysis; orchestrator-precomputed
)


def strip_non_runtime_sections(content: str) -> str:
    """Strips non-runtime sections from SKILL.md for runtime prompt efficiency."""
    lines = content.splitlines()
    out = []
    skipping = False
    for line in lines:
        if line.startswith("## "):
            skipping = any(line.startswith(m) for m in _STRIP_SECTIONS_STARTING_WITH)
        if not skipping:
            out.append(line)
    return "\n".join(out).strip()


class AgentRegistryClient:
    """REST client for Google Cloud Agent Registry API."""

    def __init__(
        self,
        project_id: str,
        location: str,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.project_id = project_id
        self.location = location
        self._http_client = http_client
        self._owns_client = http_client is None
        self._ssl_context: ssl.SSLContext | None = None

        env_base_url = os.environ.get("AGENT_REGISTRY_BASE_URL")
        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        elif env_base_url:
            self.base_url = env_base_url.rstrip("/")
        else:
            # Automatic mTLS resolution
            mtls_setting = os.getenv("GOOGLE_API_USE_MTLS_ENDPOINT", "auto").lower()
            if mtls_setting != "never":
                self._ssl_context = _create_mtls_ssl_context()
                if self._ssl_context is not None or mtls_setting == "always":
                    self.base_url = DEFAULT_MTLS_BASE_URL
                else:
                    self.base_url = DEFAULT_BASE_URL
            else:
                self.base_url = DEFAULT_BASE_URL

        if ".mtls.googleapis.com" in self.base_url and self._ssl_context is None:
            self._ssl_context = _create_mtls_ssl_context()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            credentials, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            if not credentials.valid:
                try:
                    credentials.refresh(GoogleAuthRequest())
                except Exception:
                    logger.exception("Initial credential refresh in _get_client failed")
            self._http_client = httpx.AsyncClient(
                auth=GoogleAuth(credentials, quota_project_id=self.project_id),
                verify=self._ssl_context if self._ssl_context is not None else True,
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._http_client

    async def close(self) -> None:
        """Close the underlying HTTP client if owned."""
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def list_authorized_skills(self) -> list[Skill]:
        """Paginated GET .../skills, filters out TARGET_STATE_DISABLED."""
        client = await self._get_client()
        parent = f"projects/{self.project_id}/locations/{self.location}"
        base_url = f"{self.base_url}/{parent}/skills"

        all_skills: list[Skill] = []
        page_token = ""

        while True:
            params = {}
            if page_token:
                params["pageToken"] = page_token

            response = await client.get(base_url, params=params)
            if response.status_code != 200:
                logger.error(
                    "Agent Registry list_authorized_skills failed: status=%s url=%s body=%s",
                    response.status_code,
                    base_url,
                    response.text,
                )
                raise RuntimeError(f"Agent Registry {response.status_code} on GET {base_url}: {response.text}")

            data = response.json()
            skills_data = data.get("skills", [])
            for item in skills_data:
                target_state = item.get("targetState", "")
                if target_state != "TARGET_STATE_DISABLED":
                    all_skills.append(
                        Skill(
                            name=item.get("name", ""),
                            target_state=target_state,
                            default_revision=item.get("defaultRevision", ""),
                        )
                    )

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            page_token = next_page_token

        return all_skills

    async def get_skill_content(self, skill_id: str) -> str:
        """Resolve private-{skill_id} -> defaultRevision -> zip -> SKILL.md text."""
        client = await self._get_client()

        # ADR-0006 specifies: private-{skill}
        formatted_id = skill_id if skill_id.startswith("private-") else f"private-{skill_id}"
        skill_name = f"projects/{self.project_id}/locations/{self.location}/skills/{formatted_id}"

        # 1. Fetch skill metadata to get defaultRevision
        skill_url = f"{self.base_url}/{skill_name}"
        response = await client.get(skill_url)
        if response.status_code != 200:
            logger.error(
                "Agent Registry get_skill failed: status=%s url=%s body=%s",
                response.status_code,
                skill_url,
                response.text,
            )
            raise RuntimeError(f"Agent Registry {response.status_code} on GET {skill_url}: {response.text}")

        skill_data = response.json()
        default_revision = skill_data.get("defaultRevision", "")
        if not default_revision:
            raise ValueError(f"skill {skill_name} has no default revision")

        # 2. Fetch revision content as ZIP (?alt=media)
        rev_url = f"{self.base_url}/{default_revision}"
        rev_response = await client.get(rev_url, params={"alt": "media"})
        if rev_response.status_code != 200:
            logger.error(
                "Agent Registry get_revision failed: status=%s url=%s body=%s",
                rev_response.status_code,
                rev_url,
                rev_response.text,
            )
            raise RuntimeError(f"Agent Registry {rev_response.status_code} on GET {rev_url}: {rev_response.text}")

        # 3. Extract SKILL.md from zip
        try:
            with zipfile.ZipFile(io.BytesIO(rev_response.content)) as zf:
                for filename in zf.namelist():
                    if filename == "SKILL.md" or filename.endswith("/SKILL.md"):
                        with zf.open(filename) as f:
                            raw_text = f.read().decode("utf-8")
                            return strip_non_runtime_sections(raw_text)
                raise ValueError("SKILL.md not found in revision zip")
        except zipfile.BadZipFile as e:
            raise ValueError(f"failed to read zip archive: {e}") from e

    async def revoke_skill(self, skill_id: str) -> None:
        """Patches a skill's targetState to TARGET_STATE_DISABLED.

        The next call to list_authorized_skills() will filter this skill out.
        See ADR-0006 (targetState mechanism), acceptance criterion 1 in #25.

        Args:
            skill_id: Short form (e.g. "research") or full path. The `private-`
                      prefix is added if missing, mirroring get_skill_content's
                      behavior.
        """
        await self._patch_target_state(skill_id, "TARGET_STATE_DISABLED")

    async def restore_skill(self, skill_id: str) -> None:
        """Patches a skill's targetState back to TARGET_STATE_ACTIVE.

        Symmetric to revoke_skill — used by the demo runner to reset state
        between runs.
        """
        await self._patch_target_state(skill_id, "TARGET_STATE_ACTIVE")

    async def _patch_target_state(self, skill_id: str, target_state: str) -> None:
        """Shared PATCH implementation for revoke/restore.

        Uses the standard Google API pattern: PATCH with updateMask=targetState.
        """
        if target_state not in ("TARGET_STATE_ACTIVE", "TARGET_STATE_DISABLED"):
            raise ValueError(f"Invalid target_state '{target_state}'; must be ACTIVE or DISABLED")

        client = await self._get_client()
        formatted_id = skill_id if skill_id.startswith("private-") else f"private-{skill_id}"
        skill_name = f"projects/{self.project_id}/locations/{self.location}/skills/{formatted_id}"
        url = f"{self.base_url}/{skill_name}"

        body = {"targetState": target_state}
        # updateMask ensures only targetState is modified — never touch defaultRevision etc.
        params = {"updateMask": "targetState"}

        response = await client.patch(url, json=body, params=params)
        if response.status_code not in (200, 204):
            logger.error(
                "Agent Registry PATCH failed: status=%s url=%s body=%s",
                response.status_code,
                url,
                response.text,
            )
            raise RuntimeError(
                f"Failed to PATCH skill {skill_name} to {target_state}: "
                f"status={response.status_code} body={response.text}"
            )
