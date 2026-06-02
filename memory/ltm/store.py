import os

from dotenv import load_dotenv
from langgraph.store.postgres import PostgresStore

load_dotenv()


def get_store():
    return PostgresStore.from_conn_string(os.environ["DATABASE_URL"])
