"""Example GitLab metrics implementations."""
from __future__ import annotations

from statistics import mean

from .base import Metric, MetricResult
from ..api.gitlab_client import GitLabClient
from ..config import get_settings

class GitLabProjectsCountMetric(Metric):
    key = "gitlab_projects_count"
    label = "GitLab Projects Count"
    source = "gitlab"

    def compute(self) -> MetricResult:  # noqa: D401
        client = GitLabClient()
        projects = client.list_projects()
        return MetricResult(self.key, self.label, len(projects), "Configured GitLab projects accessible")

class GitLabMergeRequestThroughputMetric(Metric):
    key = "gitlab_mr_throughput"
    label = "GitLab MR Throughput (recent)"
    source = "gitlab"

    def compute(self) -> MetricResult:  # noqa: D401
        if not get_settings().features.include_deploy_frequency:
            return MetricResult(self.key, self.label, None, "Deploy frequency disabled by feature flag")
        client = GitLabClient()
        total = 0
        for pid in get_settings().gitlab.project_ids:
            merges = client.recent_merges(pid, per_page=20)
            total += len(merges)
        return MetricResult(self.key, self.label, total, "Merged MRs across configured projects (last page)")
