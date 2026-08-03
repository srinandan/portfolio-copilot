import os
from unittest.mock import AsyncMock, patch

import pytest
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from src.orchestrator.session_manager import SessionManager


@pytest.mark.asyncio
async def test_session_manager_in_memory():
    manager = SessionManager(use_in_memory=True)
    assert isinstance(manager.session_service, InMemorySessionService)
    assert isinstance(manager.memory_service, InMemoryMemoryService)

    session = await manager.get_or_create_session("test_app", "test_user")
    assert session is not None
    assert session.app_name == "test_app"
    assert session.user_id == "test_user"

    session2 = await manager.get_or_create_session("test_app", "test_user", session.id)
    assert session2.id == session.id


@pytest.mark.asyncio
async def test_session_manager_no_agent_engine_id():
    with patch.dict(os.environ, clear=True):
        manager = SessionManager(use_in_memory=False)
        assert isinstance(manager.session_service, InMemorySessionService)
        assert isinstance(manager.memory_service, InMemoryMemoryService)


@pytest.mark.asyncio
async def test_session_manager_get_or_create_session_error():
    manager = SessionManager(use_in_memory=True)

    manager.session_service.get_session = AsyncMock(side_effect=Exception("mocked error"))
    manager.session_service.create_session = AsyncMock(return_value="mocked_session")

    session = await manager.get_or_create_session("test_app", "test_user", "invalid_id")
    assert session == "mocked_session"


@pytest.mark.asyncio
async def test_session_manager_add_memory_no_memory_service():
    manager = SessionManager(use_in_memory=True)
    manager.memory_service = None

    await manager.add_session_to_memory("test_app", "test_user", "some_id")


@pytest.mark.asyncio
@patch.dict(os.environ, {"AGENT_ENGINE_ID": "test-agent-id"})
async def test_session_manager_add_memory():
    manager = SessionManager(use_in_memory=True)
    session = await manager.get_or_create_session("test_app", "test_user")

    # This should just print an error and not crash since InMemory doesn't support add_session_to_memory
    await manager.add_session_to_memory("test_app", "test_user", session.id)


@patch("src.orchestrator.session_manager.VertexAiSessionService")
@patch("src.orchestrator.session_manager.VertexAiMemoryBankService")
def test_session_manager_vertex_ai(mock_memory, mock_session):
    with patch.dict(
        os.environ, {"AGENT_ENGINE_ID": "test-agent-id", "GOOGLE_CLOUD_PROJECT": "p", "GOOGLE_CLOUD_LOCATION": "l"}
    ):
        manager = SessionManager(use_in_memory=False)
        mock_session.assert_called_once_with(project="p", location="l")
        mock_memory.assert_called_once_with(project="p", location="l", agent_engine_id="test-agent-id")
