from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

load_dotenv()


@asynccontextmanager
async def get_checkpointer():

    async with AsyncPostgresSaver.from_conn_string(
        os.environ["DATABASE_URL"]
    ) as checkpointer:
        yield checkpointer
