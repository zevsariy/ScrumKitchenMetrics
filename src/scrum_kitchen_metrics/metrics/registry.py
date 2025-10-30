"""Metric registry with auto-discovery.

Scanning strategy:
 - Iterate over modules inside scrum_kitchen_metrics.metrics (excluding private & base/registry files)
 - Import modules dynamically
 - Register subclasses of Metric automatically

Optional environment variable PLUGINS_ENABLED will later allow pluggy/entry points.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Dict, List, Type

try:
    import pluggy  # type: ignore
except Exception:  # noqa: BLE001
    pluggy = None  # type: ignore

from .base import Metric

_REGISTRY: Dict[str, Type[Metric]] = {}
_DISCOVERED = False
_PLUGIN_PROJECT_NAME = "scrum_kitchen_metrics.metrics"
_hookspec = None
_hookimpl = None
_pm = None

def register(metric_cls: Type[Metric]) -> None:
    if not hasattr(metric_cls, 'key'):
        return
    key = getattr(metric_cls, 'key')
    if key in _REGISTRY:
        # Skip duplicates silently
        return
    _REGISTRY[key] = metric_cls

def _init_plugin_manager():
    global _pm, _hookspec, _hookimpl
    if pluggy is None or _pm is not None:
        return
    _pm = pluggy.PluginManager("skm")
    _hookspec = pluggy.HookspecMarker("skm")
    _hookimpl = pluggy.HookimplMarker("skm")

    class MetricsSpec:
        @_hookspec  # type: ignore[misc]
        def skm_register_metrics(self):  # noqa: D401
            """Return an iterable of Metric subclasses to register."""

    _pm.add_hookspecs(MetricsSpec)
    _pm.load_setuptools_entrypoints("skm")

def _load_plugins():
    if pluggy is None:
        return
    _init_plugin_manager()
    if _pm is None:
        return
    # Feature flag gating (avoid plugin errors when disabled)
    try:
        from ..config import get_settings  # type: ignore
        if not get_settings().features.plugins_enabled:
            return
    except Exception:  # noqa: BLE001
        return
    for metric_classes in _pm.hook.skm_register_metrics():  # type: ignore[union-attr]
        for cls in metric_classes or []:
            register(cls)

def discover() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    package = __name__.rsplit('.', 1)[0]
    pkg_module = importlib.import_module(package)
    pkg_path = getattr(pkg_module, '__path__', [])
    # Iterate over all modules in metrics package
    for m in pkgutil.iter_modules(pkg_path):
        name = m.name
        if name.startswith('_') or name in {"base", "registry"}:
            continue
        full_name = f"{package}.{name}"
        try:
            module = importlib.import_module(full_name)
        except Exception:  # noqa: BLE001
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Metric) and obj is not Metric:
                register(obj)
    # load external plugins
    _load_plugins()
    _DISCOVERED = True

def get_metric_classes() -> List[Type[Metric]]:
    discover()
    return list(_REGISTRY.values())

__all__ = ["register", "get_metric_classes", "discover"]