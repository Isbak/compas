"""Shared Jinja2 templates instance with custom filters."""

from __future__ import annotations

from datetime import datetime

from fastapi.templating import Jinja2Templates

from ..config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _fmt_date(value: str | None, fmt: str = "%Y-%m-%d") -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime(fmt)
    except (ValueError, TypeError):
        return str(value)


def _timeago(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return str(value)
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    delta = now - dt
    secs = delta.total_seconds()
    if secs < 0:
        return _fmt_date(value)
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    if secs < 2592000:
        return f"{int(secs // 86400)}d ago"
    return _fmt_date(value)


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{round(value * 100)}%" if value <= 1 else f"{round(value)}%"


def _filesize(value: int | None) -> str:
    if not value:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def render(name: str, context: dict, **kwargs):
    """Render a template, adapting to Starlette's request-first signature."""
    return templates.TemplateResponse(context["request"], name, context, **kwargs)


templates.env.filters["fmt_date"] = _fmt_date
templates.env.filters["timeago"] = _timeago
templates.env.filters["pct"] = _pct
templates.env.filters["filesize"] = _filesize
