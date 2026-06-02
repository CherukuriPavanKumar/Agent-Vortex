import uuid
import os
import psycopg


# Resolved lazily so the module can be imported even before .env is loaded.
# Each function calls _get_db_url() which raises a clear error if missing.
def _get_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Copy .env.example to .env and fill in your PostgreSQL connection string."
        )
    return url


def create_conversation():
    conversation_id = str(uuid.uuid4())

    with psycopg.connect(_get_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations(id)
                VALUES(%s)
                """,
                (conversation_id,),
            )

        conn.commit()

    return conversation_id


def list_conversations():
    with psycopg.connect(_get_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    title,
                    created_at
                FROM conversations
                ORDER BY created_at DESC
                """
            )

            return cur.fetchall()


def get_conversation(conversation_id):
    with psycopg.connect(_get_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM conversations
                WHERE id = %s
                """,
                (conversation_id,),
            )

            return cur.fetchone()


def update_title(conversation_id, title):
    with psycopg.connect(_get_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversations
                SET title = %s
                WHERE id = %s
                """,
                (title, conversation_id),
            )

        conn.commit()
