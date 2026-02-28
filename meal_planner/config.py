"""Key-value settings storage backed by the SQLite settings table.

Known keys:
    claude_api_key  — Anthropic API key for AI features (stored as-is, never exported).
"""

from meal_planner.db.database import get_connection


def get_setting(key: str, default: str = None) -> str:
    """Return the value for a settings key, or default if not found."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    """Insert or update a settings key-value pair (upsert)."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()
