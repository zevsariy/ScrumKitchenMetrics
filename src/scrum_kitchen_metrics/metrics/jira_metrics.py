"""Example JIRA metrics implementations."""
from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import List

from .base import Metric, MetricResult
from ..api.jira_client import JiraClient
from ..config import get_settings

class JiraIssueCountMetric(Metric):
    key = "jira_issue_count"
    label = "JIRA Issues Count"
    source = "jira"

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        jql = settings.jql_filter or "project = DEMO"
        with JiraClient() as client:
            issues = client.search_issues(jql)
        return MetricResult(self.key, self.label, len(issues), "Total issues returned by JQL")

class JiraAverageCycleTimeMetric(Metric):
    key = "jira_cycle_time_avg"
    label = "Average Cycle Time (days)"
    source = "jira"

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not get_settings().features.include_cycle_time:
            return MetricResult(self.key, self.label, None, "Cycle time disabled by feature flag")
        jql = settings.jql_filter or "project = DEMO"
        with JiraClient() as client:
            issues = client.search_issues(jql)
        cycle_times: List[float] = []
        for issue in issues:
            fields = issue.get("fields", {})
            created = fields.get("created")
            resolved = fields.get("resolutiondate")
            if created and resolved:
                try:
                    d1 = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    d2 = datetime.fromisoformat(resolved.replace('Z', '+00:00'))
                    cycle_times.append((d2 - d1).total_seconds() / 86400.0)
                except ValueError:
                    continue
        value = round(mean(cycle_times), 2) if cycle_times else None
        return MetricResult(self.key, self.label, value, "Average days from creation to resolution")
