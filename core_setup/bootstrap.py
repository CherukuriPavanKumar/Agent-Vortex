import os
import psycopg
from dotenv import load_dotenv
from core_setup.checkpointer import get_checkpointer
from memory.ltm.store import get_store


async def bootstrap_database():
    """Ensures all necessary PostgreSQL tables are created before the app starts."""
    print("Bootstrapping database...")
    load_dotenv()

    try:
        # 1. Setup conversations table (sync)
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id UUID PRIMARY KEY,
                        title TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
            conn.commit()
        print("Conversations table verified.")

        # 2. Setup Checkpointer (async)
        async with get_checkpointer() as checkpointer:
            await checkpointer.setup()
        print("Checkpoint tables verified.")

        # 3. Setup LTM Store (sync)
        with get_store() as store:
            store.setup()
        print("LTM Store tables verified.")

    except Exception as e:
        print(f"Error during bootstrap: {e}")
        print("Make sure PostgreSQL is running and DATABASE_URL is correct.")
        raise e
