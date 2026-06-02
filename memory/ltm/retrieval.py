from memory.ltm.store import get_store


def get_memories(user_id):

    namespace = ("users", user_id, "memories")

    with get_store() as store:
        memories = store.search(namespace)

    return memories
