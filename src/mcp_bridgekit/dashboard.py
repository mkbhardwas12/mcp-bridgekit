from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .config import settings

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent.parent / "templates"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/architecture", response_class=HTMLResponse)
async def architecture(request: Request):
    return templates.TemplateResponse("architecture.html", {"request": request})


@router.get("/dashboard/data")
async def dashboard_data(request: Request):
    bridge = request.app.state.bridge
    stats = bridge.get_stats()
    return {
        **stats,
        "logs": list(bridge.recent_logs),
        "tools": bridge.get_all_tool_names(),
    }
