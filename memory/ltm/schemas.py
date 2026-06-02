from pydantic import BaseModel, Field


class SemanticMemory(BaseModel):
    memory_type: str = Field(
        description="Category of memory (e.g., preference, fact, goal, skill, project)"
    )
    content: str = Field(
        description="The actual memory content in normalized format (e.g., 'User prefers Fedora Linux', 'User\\'s name is Pavan')"
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0 that this is a persistent fact"
    )
