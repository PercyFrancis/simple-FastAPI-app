from simple_fastapi_app.database.core import get_connection


def get_item(*, item_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, number FROM items WHERE id = %s",
                (item_id,),
            )
            return cur.fetchone()


def upsert_item(*, item_id: str, number: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO items (id, name, number)
                VALUES (%s, %s, %s)
                ON CONFLICT (id)
                DO UPDATE SET number = EXCLUDED.number
                """,
                (item_id, item_id, number),
            )

    return {"name": item_id, "number": number}


def get_all_items():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, number FROM items")
            rows = cur.fetchall()

    return {
        row["id"]: {
            "name": row["name"],
            "number": row["number"],
        }
        for row in rows
    }