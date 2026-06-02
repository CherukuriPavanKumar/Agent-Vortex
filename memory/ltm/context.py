from memory.ltm.retrieval import get_memories


def build_memory_context(user_id: str):

    memories = get_memories(user_id)

    if not memories:
        return ""

    memory_lines = []

    for memory in memories:
        memory_lines.append(f"- {memory.value['content']}")

    return "\n".join(memory_lines)
