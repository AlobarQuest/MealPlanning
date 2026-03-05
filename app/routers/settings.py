from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core.ai_assistant import get_api_key_status

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request):
    status = get_api_key_status()
    return templates.TemplateResponse(request, "settings.html", {
        "active_tab": "settings",
        "demo": False,
        "key_set": status["set"],
        "key_source": status["source"],
    })
