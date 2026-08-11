import io
import json
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
        assert request.url.path == "/v1alpha/projects/test-project/locations/test-location/skills"
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
        base_url="https://agentregistry.googleapis.com/v1alpha",
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

    with pytest.raises(RuntimeError, match=r"Agent Registry 500 on GET .*Internal Server Error"):
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
            assert request.url.path == "/v1alpha/projects/p/locations/l/skills/private-my-skill/revisions/rev1"
            zip_bytes = create_zip({"SKILL.md": "# My Skill Doc"})
            return httpx.Response(200, content=zip_bytes)

        assert request.url.path == "/v1alpha/projects/test-project/locations/test-location/skills/private-my-skill"
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

    with pytest.raises(RuntimeError, match=r"Agent Registry 404 on GET .*Skill not found"):
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

    with pytest.raises(RuntimeError, match=r"Agent Registry 500 on GET .*Failed to download zip"):
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


def test_google_auth_before_request():
    mock_creds = MagicMock()

    def before_request(req, method, url, headers):
        headers["Authorization"] = "Bearer test-token"

    mock_creds.before_request = MagicMock(side_effect=before_request)

    auth = GoogleAuth(mock_creds)
    req = httpx.Request("GET", "https://example.com")
    flow = auth.auth_flow(req)
    next(flow)

    assert mock_creds.before_request.called
    assert req.headers["Authorization"] == "Bearer test-token"


def test_google_auth_fallback():
    class CustomCreds:
        valid = False
        token = None

        def refresh(self, req):
            self.valid = True
            self.token = "custom-token"

    creds = CustomCreds()
    auth = GoogleAuth(creds)
    req = httpx.Request("GET", "https://example.com")
    flow = auth.auth_flow(req)
    next(flow)

    assert creds.valid is True
    assert req.headers["Authorization"] == "Bearer custom-token"


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


@pytest.mark.asyncio
async def test_revoke_skill_patches_target_state():
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"name": "test"})

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.revoke_skill("research")
    assert captured_request is not None
    assert captured_request.method == "PATCH"
    assert "private-research" in str(captured_request.url)
    assert "updateMask=targetState" in str(captured_request.url)
    assert json.loads(captured_request.content) == {"targetState": "TARGET_STATE_DISABLED"}


@pytest.mark.asyncio
async def test_restore_skill_patches_target_state_active():
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"name": "test"})

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.restore_skill("research")
    assert captured_request is not None
    assert json.loads(captured_request.content) == {"targetState": "TARGET_STATE_ACTIVE"}


@pytest.mark.asyncio
async def test_revoke_skill_adds_private_prefix_when_missing():
    urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json={})

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.revoke_skill("research")
    await client.revoke_skill("private-research")
    assert len(urls) == 2
    assert urls[0] == urls[1]


@pytest.mark.asyncio
async def test_revoke_skill_raises_on_non_2xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    client = AgentRegistryClient(
        project_id="test-project",
        location="test-location",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(RuntimeError, match="Failed to PATCH skill"):
        await client.revoke_skill("research")


@pytest.mark.asyncio
async def test_patch_target_state_rejects_invalid_state():
    client = AgentRegistryClient(project_id="test-project", location="test-location")
    with pytest.raises(ValueError, match="Invalid target_state"):
        await client._patch_target_state("research", "TARGET_STATE_BOGUS")


def test_google_auth_attaches_quota_project_header():
    mock_creds = MagicMock()
    mock_creds.quota_project_id = None
    mock_creds.before_request = MagicMock()

    auth = GoogleAuth(mock_creds, quota_project_id="quota-proj")
    req = httpx.Request("GET", "https://example.com")
    flow = auth.auth_flow(req)
    next(flow)

    assert req.headers["x-goog-user-project"] == "quota-proj"


def test_registry_client_mtls_auto_resolution():
    with patch("orchestrator.registry_client.mtls.has_default_client_cert_source", return_value=True):
        with patch(
            "orchestrator.registry_client.mtls.default_client_cert_source",
            return_value=lambda: (b"cert", b"key"),
        ):
            with patch("orchestrator.registry_client.ssl.create_default_context") as mock_ssl_ctx:
                mock_ctx_inst = MagicMock()
                mock_ssl_ctx.return_value = mock_ctx_inst

                client = AgentRegistryClient(project_id="test-p", location="global")
                assert "agentregistry.mtls.googleapis.com" in client.base_url
                assert client._ssl_context == mock_ctx_inst


def test_registry_client_mtls_disabled():
    with patch.dict("os.environ", {"GOOGLE_API_USE_MTLS_ENDPOINT": "never"}):
        client = AgentRegistryClient(project_id="test-p", location="global")
        assert "agentregistry.googleapis.com" in client.base_url
        assert client._ssl_context is None


def test_registry_client_env_base_url_override():
    with patch.dict("os.environ", {"AGENT_REGISTRY_BASE_URL": "https://custom-registry.internal"}):
        client = AgentRegistryClient(project_id="test-p", location="global")
        assert client.base_url == "https://custom-registry.internal"


@pytest.mark.asyncio
async def test_get_skill_content_strips_non_runtime_sections():
    raw_skill_md = """# Research Skill

## Purpose
Gathers market context.

## Output
Research brief summary.

## Registry metadata
- Version: 0.1.0

## Acceptance criteria
1. Must not leak sensitive data.
2. Must cite run id.
"""
    zip_bytes = create_zip({"SKILL.md": raw_skill_md})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/skills/private-research"):
            return httpx.Response(200, json={"defaultRevision": "revisions/rev1"})
        if request.url.path.endswith("/revisions/rev1"):
            return httpx.Response(200, content=zip_bytes)
        return httpx.Response(404)

    client = AgentRegistryClient(
        project_id="test-p",
        location="global",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    stripped = await client.get_skill_content("research")
    assert "## Purpose" in stripped
    assert "## Output" in stripped
    assert "## Registry metadata" not in stripped
    assert "## Acceptance criteria" not in stripped
    assert "Must not leak sensitive data" not in stripped


def test_strip_removes_middle_sections_but_keeps_later_ones():
    from orchestrator.registry_client import strip_non_runtime_sections

    content = """# Action Drafting

## Purpose
Drafts trades.

## Drafting logic
Compute math and allocations here.

## Output
Author rationale only.

## Acceptance criteria
1. Valid trade.
"""
    stripped = strip_non_runtime_sections(content)
    assert "## Purpose" in stripped
    assert "## Output" in stripped
    assert "Author rationale only." in stripped
    assert "## Drafting logic" not in stripped
    assert "Compute math and allocations here." not in stripped
    assert "## Acceptance criteria" not in stripped
    assert "Valid trade." not in stripped
