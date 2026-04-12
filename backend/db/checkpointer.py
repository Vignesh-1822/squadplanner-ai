"""MongoDB-backed checkpointer for LangGraph human-in-the-loop."""

from typing import Any


class MongoDBCheckpointer:
    """Persist graph state in MongoDB for resume / HITL."""

    def __init__(self, collection_name: str = "langgraph_checkpoints"):
        self._collection_name = collection_name

    async def get(self, thread_id: str) -> dict[str, Any] | None:
        return None

    async def put(self, thread_id: str, checkpoint: dict[str, Any]) -> None:
        return None
