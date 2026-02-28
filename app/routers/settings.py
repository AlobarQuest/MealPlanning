from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from meal_planner.config import get_setting, set_setting

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, saved: str = ""):
    key = get_setting("claude_api_key") or ""
    masked = key[:8] + "..." if len(key) > 8 else ""
    return templates.TemplateResponse(request, "settings.html", {
        "active_tab": "settings",
        "demo": False,
        "key_set": bool(key),
        "masked_key": masked,
        "flash_message": "Settings saved." if saved else None,
        "flash_type": "success",
    })


@router.post("")
def settings_save(claude_api_key: str = Form("")):
    if claude_api_key.strip():
        set_setting("claude_api_key", claude_api_key.strip())
    return RedirectResponse(url="/settings?saved=1", status_code=303)
