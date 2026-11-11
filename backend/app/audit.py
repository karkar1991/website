from psycopg.types.json import Jsonb


def log(conn, admin_id: int | None, action: str, target_id: int | None = None, detail: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_logs (admin_id, action, target_id, detail) VALUES (%s, %s, %s, %s)",
        (admin_id, action, target_id, Jsonb(detail or {})),
    )
