"""SQLite database connection management and schema initialization.

Provides a single-file database at ~/.meal_planner/meal_planner.db.
Every public function that needs a connection should call get_connection(),
use it, and close it in a finally block.
"""

import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_db_path_override: ContextVar["Path | None"] = ContextVar("_db_path_override", default=None)


@contextmanager
def override_db_path(path: "Path"):
    """Context manager to override the DB path for the current async task/thread.

    Used by demo routes to serve reads from the demo DB without affecting
    other concurrent requests.

    Example:
        with override_db_path(DEMO_DB_PATH):
            items = pantry_core.get_all()
    """
    token = _db_path_override.set(path)
    try:
        yield
    finally:
        _db_path_override.reset(token)


def get_db_path() -> Path:
    """Return the active DB path.

    Priority order:
    1. ContextVar override (used by demo routes per-request)
    2. DB_PATH environment variable (used by Docker / local dev)
    3. Default ~/.meal_planner/meal_planner.db (desktop fallback)
    """
    override = _db_path_override.get()
    if override is not None:
        return override
    env_url = os.environ.get("DB_PATH")
    if env_url:
        p = Path(env_url)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    db_dir = Path.home() / ".meal_planner"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "meal_planner.db"


def get_connection(db_path: Path = None) -> sqlite3.Connection:
    """Return a new SQLite connection with Row factory and foreign keys enabled.

    Callers are responsible for closing the connection when done.
    """
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = None) -> None:
    """Create all tables if they don't already exist.

    Called once at application startup from main.py.
    Tables: stores, pantry, recipes, recipe_ingredients, meal_plan, settings.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS stores (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL UNIQUE,
            location TEXT,
            notes    TEXT
        );

        CREATE TABLE IF NOT EXISTS pantry (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode            TEXT,
            category           TEXT,
            location           TEXT,
            brand              TEXT,
            name               TEXT NOT NULL,
            quantity           REAL DEFAULT 1,
            unit               TEXT,
            stocked_date       TEXT,
            best_by            TEXT,
            preferred_store_id INTEGER REFERENCES stores(id),
            product_notes      TEXT,
            item_notes         TEXT,
            estimated_price    REAL
        );

        CREATE TABLE IF NOT EXISTS recipes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            description  TEXT,
            servings     INTEGER DEFAULT 4,
            prep_time    TEXT,
            cook_time    TEXT,
            instructions TEXT,
            source_url   TEXT,
            tags         TEXT,
            rating       INTEGER,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            name      TEXT NOT NULL,
            quantity  REAL,
            unit      TEXT,
            estimated_price REAL
        );

        CREATE TABLE IF NOT EXISTS meal_plan (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            date      TEXT NOT NULL,
            meal_slot TEXT NOT NULL,
            recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
            servings  INTEGER DEFAULT 1,
            notes     TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS staples (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            name               TEXT NOT NULL UNIQUE,
            category           TEXT,
            preferred_store_id INTEGER REFERENCES stores(id),
            need_to_buy        INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS known_prices (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name    TEXT NOT NULL UNIQUE,
            unit_price   REAL NOT NULL,
            unit         TEXT,
            store_id     INTEGER REFERENCES stores(id),
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()

    # Migrations for existing databases
    try:
        conn.execute("ALTER TABLE recipes ADD COLUMN rating INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    for col, table, col_type in [
        ("location", "stores", "TEXT"),
        ("notes", "stores", "TEXT"),
        ("estimated_price", "pantry", "REAL"),
        ("estimated_price", "recipe_ingredients", "REAL"),
        ("is_staple", "pantry", "INTEGER DEFAULT 0"),
        ("shopping_name", "recipe_ingredients", "TEXT"),
        ("shopping_qty", "recipe_ingredients", "REAL"),
        ("shopping_unit", "recipe_ingredients", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Migrate pantry is_staple items to standalone staples table
    try:
        rows = conn.execute(
            "SELECT name, category, preferred_store_id FROM pantry WHERE is_staple = 1"
        ).fetchall()
        for row in rows:
            name = row["name"]
            existing = conn.execute(
                "SELECT id FROM staples WHERE LOWER(name) = LOWER(?)", (name,)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO staples (name, category, preferred_store_id, need_to_buy) VALUES (?, ?, ?, 0)",
                    (name, row["category"], row["preferred_store_id"]),
                )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # is_staple column may not exist yet on fresh installs

    conn.close()
