from memory.ltm.extractor import extract_memories
from memory.ltm.retrieval import get_memories
from memory.ltm.store_memory import store_memory


async def extract_and_store_memories(messages, user_id: str = "default_user"):
    """
    Standalone service to extract memories from a conversation transcript and store them.
    Limits processing to the last 30 messages to avoid huge prompts.
    Does not crash on LLM or quota failures.
    """
    print("\n[LTM] Running background memory extraction...")

    if not messages:
        print("[LTM] No messages to process.")
        return

    # 1. Build transcript from the last 30 messages
    recent_messages = messages[-30:]
    conversation_text = ""

    for msg in recent_messages:
        if not getattr(msg, "content", None):
            continue
        conversation_text += f"{msg.__class__.__name__}: {msg.content}\n"

    if not conversation_text.strip():
        print("[LTM] Empty conversation text. Skipping.")
        return

    # 2. Run extractor safely
    try:
        memory_result = await extract_memories(conversation_text)
    except Exception as e:
        print(f"[LTM Error] Extraction failed: {e}")
        return

    if not memory_result or not memory_result.memories:
        print("[LTM] No persistent memories detected.")
        return

    # 3. Deduplicate
    try:
        existing = get_memories(user_id)
        existing_contents = {m.value["content"].lower().strip() for m in existing}
    except Exception as e:
        print(f"[LTM Error] Failed to fetch existing memories for deduplication: {e}")
        return

    # 4. Store memories
    stored_count = 0
    for memory in memory_result.memories:
        content = memory.content.lower().strip()

        if content in existing_contents:
            continue

        try:
            store_memory(user_id, memory)
            stored_count += 1
            existing_contents.add(content)  # Prevent duplicates within the same batch
        except Exception as e:
            print(f"[LTM Error] Failed to store memory '{memory.content}': {e}")
            continue

    print(f"[LTM] Extraction complete. Stored {stored_count} new memories.")
