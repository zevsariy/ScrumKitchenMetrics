"""Base abstractions for metrics computation."""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class MetricResult:
    key: str
    label: str
    value: Any
    description: str | None = None
    extra: Dict[str, Any] | None = None

class Metric(abc.ABC):
    key: str
    label: str
    description: str | None = None
    source: str | None = None  # e.g. 'jira', 'gitlab', 'custom'

    @abc.abstractmethod
    def compute(self) -> MetricResult:
        ...

__all__ = ["Metric", "MetricResult"]
