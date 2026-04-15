from __future__ import annotations

from .harness import AgentHarness


class ChatService(AgentHarness):
    def chat(self, session_id: str, message: str):
        return self.handle_message(session_id, message, source="http")
