"""Agent Registry REST client."""

import io
import zipfile
from dataclasses import dataclass
from typing import Any

import httpx
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest

DEFAULT_BASE_URL = "https://agentregistry.googleapis.com/v1"


@dataclass
class Skill:
    name: str
    target_state: str = ""
    default_revision: str = ""


class GoogleAuth(httpx.Auth):
    """httpx Auth flow using Google credentials."""

    def __init__(self, credentials: Any):
        self.credentials = credentials
        self._auth_request = GoogleAuthRequest()

    def auth_flow(self, request: httpx.Request):
        if not self.credentials.valid:
            self.credentials.refresh(self._auth_request)
        self.credentials.apply(request.headers)
        yield request


class AgentRegistryClient:
    """REST client for Google Cloud Agent Registry API."""

    def __init__(
        self,
        project_id: str,
        location: str,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.project_id = project_id
        self.location = location
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client
        self._owns_client = http_client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            credentials, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            self._http_client = httpx.AsyncClient(auth=GoogleAuth(credentials))
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
                raise RuntimeError(f"API returned status {response.status_code}: {response.text}")

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
            raise RuntimeError(f"API returned status {response.status_code}: {response.text}")

        skill_data = response.json()
        default_revision = skill_data.get("defaultRevision", "")
        if not default_revision:
            raise ValueError(f"skill {skill_name} has no default revision")

        # 2. Fetch revision content as ZIP (?alt=media)
        rev_url = f"{self.base_url}/{default_revision}"
        rev_response = await client.get(rev_url, params={"alt": "media"})
        if rev_response.status_code != 200:
            raise RuntimeError(f"API returned status {rev_response.status_code} fetching revision: {rev_response.text}")

        # 3. Extract SKILL.md from zip
        try:
            with zipfile.ZipFile(io.BytesIO(rev_response.content)) as zf:
                for filename in zf.namelist():
                    if filename == "SKILL.md" or filename.endswith("/SKILL.md"):
                        with zf.open(filename) as f:
                            return f.read().decode("utf-8")
                raise ValueError("SKILL.md not found in revision zip")
        except zipfile.BadZipFile as e:
            raise ValueError(f"failed to read zip archive: {e}") from e
