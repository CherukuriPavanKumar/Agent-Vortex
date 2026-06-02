import uuid

from memory.ltm.store import get_store


def store_memory(user_id, memory):
    namespace = ("users", user_id, "memories")

    key = str(uuid.uuid4())

    with get_store() as store:
        store.put(
            namespace,
            key,
            {
                "memory_type": memory.memory_type,
                "content": memory.content,
                "confidence": memory.confidence,
            },
        )
