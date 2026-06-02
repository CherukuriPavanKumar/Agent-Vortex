from pydantic import BaseModel, Field


class Plan(BaseModel):
    plan: list[str] = Field(
        default_factory=list,
        description="Step-by-step execution plan."
    )

    tools: list[str] = Field(
        default_factory=list,
        description="Exact tool names required."
    )