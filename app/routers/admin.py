import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from meal_planner.db.database import get_db_path, get_connection
from meal_planner.config import get_setting, set_setting

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

_SQLITE_MAGIC = b"SQLite format 3\x00"


def _migration_done() -> bool:
    return get_setting("migration_done") == "1"


@router.get("/migrate", response_class=HTMLResponse)
def migrate_page(request: Request):
    return templates.TemplateResponse(request, "admin_migrate.html", {
        "active_tab": None,
        "demo": False,
        "done": _migration_done(),
    })


@router.post("/migrate", response_class=HTMLResponse)
def do_migrate(request: Request, db_file: UploadFile = File(...)):
    if _migration_done():
        return templates.TemplateResponse(request, "admin_migrate.html", {
            "active_tab": None,
            "demo": False,
            "done": True,
        })

    data = db_file.file.read()

    if not data.startswith(_SQLITE_MAGIC):
        return templates.TemplateResponse(request, "admin_migrate.html", {
            "active_tab": None,
            "demo": False,
            "done": False,
            "error": "The uploaded file does not appear to be a valid SQLite database.",
        })

    db_path = get_db_path()

    # Write to a temp file alongside the target, then atomically replace
    tmp = Path(tempfile.mktemp(dir=db_path.parent, suffix=".db.tmp"))
    try:
        tmp.write_bytes(data)
        # Mark migration done inside the uploaded DB before replacing
        conn = None
        try:
            import sqlite3
            conn = sqlite3.connect(str(tmp))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('migration_done', '1')"
            )
            conn.commit()
        finally:
            if conn:
                conn.close()
        tmp.replace(db_path)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return templates.TemplateResponse(request, "admin_migrate.html", {
            "active_tab": None,
            "demo": False,
            "done": False,
            "error": f"Migration failed: {e}",
        })

    return RedirectResponse(url="/pantry?migrated=1", status_code=303)
