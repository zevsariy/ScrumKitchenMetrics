"""Minimal GitLab client using python-gitlab library for convenience."""
from __future__ import annotations

from typing import Any, Dict, List

import gitlab  # type: ignore

from ..config import get_settings

class GitLabClient:
    name = "gitlab"

    def __init__(self):
        settings = get_settings().gitlab
        if not settings.base_url:
            raise ValueError("GITLAB_BASE_URL not configured")
        self._gl = gitlab.Gitlab(settings.base_url, private_token=settings.private_token, ssl_verify=settings.verify_ssl)

    def list_projects(self) -> List[Dict[str, Any]]:  # noqa: D401
        out = []
        for pid in get_settings().gitlab.project_ids:
            try:
                proj = self._gl.projects.get(pid)
            except gitlab.GitlabGetError:  # type: ignore
                continue
            out.append({"id": proj.id, "name": proj.name, "path_with_namespace": proj.path_with_namespace})
        return out

    def recent_merges(self, project_id: int, per_page: int = 20):  # noqa: D401
        proj = self._gl.projects.get(project_id)
        return proj.mergerequests.list(state='merged', per_page=per_page)
