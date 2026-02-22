from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent.parent / "templates"))

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/dashboard/data")
async def dashboard_data(request: Request):
    bridge = request.app.state.bridge
    return {
        "sessions": len(bridge.sessions),
        "jobs": bridge.queue.count if hasattr(bridge, 'queue') else 0,
        "logs": list(bridge.recent_logs) if hasattr(bridge, 'recent_logs') else [],
        "tools": list(bridge.known_tools) if hasattr(bridge, 'known_tools') else ["analyze_data"],
    }
