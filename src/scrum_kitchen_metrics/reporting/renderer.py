"""Jinja2 renderer for HTML reports."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import get_settings

_env_cache: Environment | None = None

def get_jinja_env() -> Environment:
    global _env_cache
    if _env_cache is None:
        cfg = get_settings().report
        loader = FileSystemLoader(str(cfg.template_dir))
        _env_cache = Environment(loader=loader, autoescape=select_autoescape(['html', 'xml']))
    return _env_cache

def render_template(template_name: str, context: Dict[str, Any]) -> str:
    env = get_jinja_env()
    template = env.get_template(template_name)
    return template.render(**context)
