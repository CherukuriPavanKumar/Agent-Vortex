from functools import lru_cache
from pathlib import Path

import os
import yaml

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

load_dotenv()

_CONFIG_PATH = (
    Path(__file__).parent.parent
    / "config.yaml"
)


def load_config() -> dict:
    return yaml.safe_load(
        _CONFIG_PATH.read_text()
    )


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    config = load_config()["llm"]

    return ChatOpenAI(
        model=config["model"],
        api_key=os.environ[
            "OPENROUTER_API_KEY"
        ],
        base_url="https://openrouter.ai/api/v1",
        temperature=config["temperature"],
        timeout=config["timeout"],
    )


async def invoke(
    messages: list[BaseMessage],
    tools=None,
):
    llm = get_llm()

    if tools:
        llm = llm.bind_tools(tools)

    return await llm.ainvoke(messages)


async def structured_invoke(
    messages: list[BaseMessage],
    schema,
):
    llm = get_llm()

    return await (
        llm.with_structured_output(schema)
        .ainvoke(messages)
    )

async def health_check():
    response = await get_llm().ainvoke(
        "Reply with exactly: OK"
    )

    return response.content


