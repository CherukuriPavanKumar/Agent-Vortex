from langchain_core.messages import HumanMessage

from core_setup.llm import invoke

async def generate_title(user_message: str):

    prompt = f"""
Generate a short conversation title.

Rules:
- 2 to 5 words
- No punctuation
- No quotes
- Be descriptive

User message:
{user_message}
"""

    response = await invoke([HumanMessage(content=prompt)])

    return response.content.strip()
