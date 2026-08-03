import io
import zipfile
from unittest.mock import MagicMock, patch

import httpx
import pytest

from orchestrator.registry_client import AgentRegistryClient, GoogleAuth, Skill


def create_zip(files: dict[str, str | bytes]) -> bytes:
    """Helper to create an in-memory zip archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_list_authorized_skills_single_page():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/projects/test-project/locations/test-location/skills"
        return httpx.Response(
            200,
            json={
                "skills": [
                    {
                        "name": "projects/test-project/locations/test-location/skills/private-a",
                        "targetState": "TARGET_STATE_ACTIVE",
                        "defaultRevision": "rev1",
                    },
                    {
                        "name": "projects/test-project/locations/test-location/skills/private-b",
                        "targetState": "TARGET_STATE_DISABLED",
                        "defaultRevision": "rev2",
                    },
                    {
                        "name": "projects/test-project/locations/test-location/skills/private-c",
                        "targetState": "TARGET_STATE_DRAFT",
                        "defaultRevision": "rev3",
                    },
                ]
            },
        )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        base_url="https://agentregistry.googleapis.com/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    skills = await client.list_authorized_skills()
    assert len(skills) == 2
    assert skills[0] == Skill(
        name="projects/test-project/locations/test-location/skills/private-a",
        target_state="TARGET_STATE_ACTIVE",
        default_revision="rev1",
    )
    assert skills[1] == Skill(
        name="projects/test-project/locations/test-location/skills/private-c",
        target_state="TARGET_STATE_DRAFT",
        default_revision="rev3",
    )


@pytest.mark.asyncio
async def test_list_authorized_skills_multiple_pages():
    req_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal req_count
        req_count += 1
        if request.url.query.decode() == "pageToken=page2":
            return httpx.Response(
                200,
                json={
                    "skills": [
                        {
                            "name": "skills/private-b",
                            "targetState": "TARGET_STATE_ACTIVE",
                            "defaultRevision": "rev2",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "skills": [
                    {
                        "name": "skills/private-a",
                        "targetState": "TARGET_STATE_ACTIVE",
                        "defaultRevision": "rev1",
                    }
                ],
                "nextPageToken": "page2",
            },
        )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    skills = await client.list_authorized_skills()
    assert req_count == 2
    assert len(skills) == 2
    assert skills[0].name == "skills/private-a"
    assert skills[1].name == "skills/private-b"


@pytest.mark.asyncio
async def test_list_authorized_skills_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(RuntimeError, match="API returned status 500"):
        await client.list_authorized_skills()


@pytest.mark.asyncio
async def test_list_authorized_skills_revocation_scenario():
    """Simulate revocation scenario: active skill -> set to DISABLED -> next call excludes it."""
    is_revoked = False

    def handler(request: httpx.Request) -> httpx.Response:
        if not is_revoked:
            return httpx.Response(
                200,
                json={
                    "skills": [
                        {
                            "name": "skills/private-revokable",
                            "targetState": "TARGET_STATE_ACTIVE",
                            "defaultRevision": "rev1",
                        }
                    ]
                },
            )
        else:
            return httpx.Response(
                200,
                json={
                    "skills": [
                        {
                            "name": "skills/private-revokable",
                            "targetState": "TARGET_STATE_DISABLED",
                            "defaultRevision": "rev1",
                        }
                    ]
                },
            )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    # Call 1: Active
    skills = await client.list_authorized_skills()
    assert len(skills) == 1
    assert skills[0].name == "skills/private-revokable"

    # Simulate revocation
    is_revoked = True

    # Call 2: Disabled
    skills = await client.list_authorized_skills()
    assert len(skills) == 0


@pytest.mark.asyncio
async def test_get_skill_content_success():
    def handler(request: httpx.Request) -> httpx.Response:
        if "alt=media" in str(request.url):
            assert request.url.path == "/v1/projects/p/locations/l/skills/private-my-skill/revisions/rev1"
            zip_bytes = create_zip({"SKILL.md": "# My Skill Doc"})
            return httpx.Response(200, content=zip_bytes)

        assert request.url.path == "/v1/projects/test-project/locations/test-location/skills/private-my-skill"
        return httpx.Response(
            200,
            json={
                "name": "projects/test-project/locations/test-location/skills/private-my-skill",
                "defaultRevision": "projects/p/locations/l/skills/private-my-skill/revisions/rev1",
            },
        )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    content = await client.get_skill_content("my-skill")
    assert content == "# My Skill Doc"


@pytest.mark.asyncio
async def test_get_skill_content_in_subdirectory():
    def handler(request: httpx.Request) -> httpx.Response:
        if "alt=media" in str(request.url):
            zip_bytes = create_zip(
                {
                    "some-dir/SKILL.md": "# Subdir Skill Doc",
                    "README.md": "# Readme",
                }
            )
            return httpx.Response(200, content=zip_bytes)

        return httpx.Response(
            200,
            json={
                "name": "projects/test-project/locations/test-location/skills/private-my-skill",
                "defaultRevision": "rev1",
            },
        )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    content = await client.get_skill_content("private-my-skill")
    assert content == "# Subdir Skill Doc"


@pytest.mark.asyncio
async def test_get_skill_content_skill_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Skill not found")

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(RuntimeError, match="API returned status 404"):
        await client.get_skill_content("nonexistent")


@pytest.mark.asyncio
async def test_get_skill_content_missing_default_revision():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "name": "projects/test-project/locations/test-location/skills/private-my-skill",
                "defaultRevision": "",
            },
        )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ValueError, match="has no default revision"):
        await client.get_skill_content("my-skill")


@pytest.mark.asyncio
async def test_get_skill_content_revision_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if "alt=media" in str(request.url):
            return httpx.Response(500, text="Failed to download zip")
        return httpx.Response(
            200,
            json={
                "name": "skills/private-my-skill",
                "defaultRevision": "rev1",
            },
        )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(RuntimeError, match="API returned status 500 fetching revision"):
        await client.get_skill_content("my-skill")


@pytest.mark.asyncio
async def test_get_skill_content_missing_skill_md():
    def handler(request: httpx.Request) -> httpx.Response:
        if "alt=media" in str(request.url):
            zip_bytes = create_zip({"other_file.txt": "some content"})
            return httpx.Response(200, content=zip_bytes)
        return httpx.Response(
            200,
            json={
                "name": "skills/private-my-skill",
                "defaultRevision": "rev1",
            },
        )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ValueError, match="SKILL.md not found in revision zip"):
        await client.get_skill_content("my-skill")


@pytest.mark.asyncio
async def test_get_skill_content_invalid_zip():
    def handler(request: httpx.Request) -> httpx.Response:
        if "alt=media" in str(request.url):
            return httpx.Response(200, content=b"invalid non-zip data")
        return httpx.Response(
            200,
            json={
                "name": "skills/private-my-skill",
                "defaultRevision": "rev1",
            },
        )

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ValueError, match="failed to read zip archive"):
        await client.get_skill_content("my-skill")


def test_google_auth():
    mock_creds = MagicMock()
    mock_creds.valid = False

    def refresh(req):
        mock_creds.valid = True

    def apply(headers):
        headers["Authorization"] = "Bearer test-token"

    mock_creds.refresh = MagicMock(side_effect=refresh)
    mock_creds.apply = MagicMock(side_effect=apply)

    auth = GoogleAuth(mock_creds)
    req = httpx.Request("GET", "https://example.com")
    flow = auth.auth_flow(req)
    next(flow)

    assert mock_creds.refresh.called
    assert req.headers["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
async def test_client_context_manager_and_default_auth():
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.apply = MagicMock()

    with patch("orchestrator.registry_client.google_auth_default", return_value=(mock_creds, "test-proj")):
        async with AgentRegistryClient(project_id="test-project", location="test-location") as client:
            http_c = await client._get_client()
            assert http_c is not None
            assert client._owns_client is True

        assert client._http_client is None
