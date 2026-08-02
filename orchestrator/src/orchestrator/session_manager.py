from orchestrator.logger import get_logger

logger = get_logger(__name__)

import os

from google.adk.memory import (
    BaseMemoryService,
    InMemoryMemoryService,
    VertexAiMemoryBankService,
)
from google.adk.sessions import (
    BaseSessionService,
    InMemorySessionService,
    VertexAiSessionService,
)


class SessionManager:
    """Manages Session and Memory Bank configuration for the orchestrator."""

    def __init__(self, use_in_memory: bool = False):
        self.project = os.environ.get("GOOGLE_CLOUD_PROJECT", "dummy-project")
        self.location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.agent_engine_id = os.environ.get("AGENT_ENGINE_ID", None)

        # Use Vertex AI services by default, fallback to InMemory for tests
        if use_in_memory or not self.agent_engine_id:
            self.session_service: BaseSessionService = InMemorySessionService()
            self.memory_service: BaseMemoryService | None = InMemoryMemoryService()
            if not use_in_memory:
                 logger.warning("AGENT_ENGINE_ID not set, falling back to InMemorySessionService and InMemoryMemoryService.")
        else:
            self.session_service = VertexAiSessionService(
                project=self.project,
                location=self.location,
            )
            self.memory_service = VertexAiMemoryBankService(
                project=self.project,
                location=self.location,
                agent_engine_id=self.agent_engine_id
            )

    async def get_or_create_session(self, app_name: str, user_id: str, session_id: str | None = None):
        if session_id:
            try:
                session = await self.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
                if session:
                    return session
            except Exception as e:
                logger.warning(f"Failed to retrieve session {session_id}: {e}")

        session = await self.session_service.create_session(app_name=app_name, user_id=user_id)
        return session

    async def add_session_to_memory(self, app_name: str, user_id: str, session_id: str):
        """Adds the specified session to the Memory Bank."""
        if not self.memory_service:
            logger.warning("Memory service not configured. Skipping.")
            return

        try:
             session = await self.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
             if session:
                 await self.memory_service.add_session_to_memory(session)
        except Exception as e:
            logger.error(f"Error adding session to memory: {e}")
