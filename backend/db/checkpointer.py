"""MongoDB-backed checkpointer for LangGraph human-in-the-loop."""

from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver

from db.client import get_database


async def get_checkpointer() -> AsyncMongoDBSaver:
    """Return an async MongoDB checkpointer for LangGraph state persistence."""
    db = get_database()
    if db.client.__class__.__module__.startswith("motor."):
        # langgraph-checkpoint-mongodb 0.2.x expects PyMongo's async client metadata hook.
        # Motor is otherwise API-compatible for the async collection operations used here.
        setattr(db.client, "append_metadata", lambda _metadata: None)
    return AsyncMongoDBSaver(db.client, db.name)
