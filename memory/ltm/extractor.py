from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from core_setup.llm import structured_invoke


class ExtractedMemory(BaseModel):
    memory_type: str = Field(
        description="Category of memory (e.g., preference, fact, goal, skill, project)"
    )
    content: str = Field(
        description="The actual memory content in normalized format (e.g., 'User prefers Fedora Linux', 'User\\'s name is Pavan')"
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0 that this is a persistent fact"
    )


class MemoryExtractionResponse(BaseModel):
    memories: list[ExtractedMemory] = Field(description="List of extracted memories")


MEMORY_EXTRACTION_PROMPT = """
You are a highly precise memory extraction system. Your job is to extract long-term, persistent facts about the user from the conversation.

### EXTRACTION TARGETS (ALWAYS REMEMBER)
- Name, identity, location, background
- Core preferences (e.g., dark mode, favorite foods, favorite OS)
- Technology choices and stacks
- Current projects, goals, and workflows
- Skills and expertise

### DO NOT EXTRACT (IGNORE)
- Temporary requests or casual greetings
- Factual questions (e.g., "What is the capital of France?")
- Search results or tool outputs
- One-off tasks (e.g., "Write an email to John")

### FORMATTING RULES (CRITICAL)
- ALL memories MUST start with "User" or "User's" (e.g., "User likes...", "User's name is...").
- Do NOT use pronouns like "He", "She", or "I".
- Keep memories concise, atomic, and factual.

### EXAMPLES

User Input: "Hi, my name is Pavan and my favourite food is biriyani. I'm building an AI OS in python."
Extracted:
1. type: "fact", content: "User's name is Pavan", confidence: 1.0
2. type: "preference", content: "User's favorite food is biriyani", confidence: 1.0
3. type: "project", content: "User is building an AI OS in Python", confidence: 1.0

User Input: "Can you search for the weather in London?"
Extracted: (Empty list)

Extract structured memories from the following conversation:
"""


async def extract_memories(conversation_text: str):
    messages = [
        SystemMessage(content=MEMORY_EXTRACTION_PROMPT),
        HumanMessage(content=conversation_text),
    ]

    return await structured_invoke(messages, MemoryExtractionResponse)
