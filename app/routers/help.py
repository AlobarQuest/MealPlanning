from pathlib import Path

import markdown
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/help", tags=["help"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

_GUIDE_PATH = Path(__file__).parent.parent.parent / "USER_GUIDE.md"


@router.get("", response_class=HTMLResponse)
def help_page(request: Request):
    text = _GUIDE_PATH.read_text(encoding="utf-8")
    content_html = markdown.markdown(text, extensions=["tables", "toc"])
    return templates.TemplateResponse(request, "help.html", {
        "active_tab": "help",
        "demo": False,
        "content_html": content_html,
    })
