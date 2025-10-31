"""Minimal JIRA client for needed endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_client import BaseAPIClient
from ..config import get_settings

class JiraClient(BaseAPIClient):
    name = "jira"

    def __init__(self):
        settings = get_settings().jira
        if not settings.base_url:
            raise ValueError("JIRA_BASE_URL not configured")
        super().__init__(settings.base_url, token=settings.api_token, verify_ssl=settings.verify_ssl)
        self._user_email = settings.user_email

    def auth_headers(self) -> Dict[str, str]:  # noqa: D401
        if not self.token or not self._user_email:
            return {}
        import base64

        creds = f"{self._user_email}:{self.token}".encode()
        token = base64.b64encode(creds).decode()
        return {"Authorization": f"Basic {token}", "Accept": "application/json"}

    def search_issues(self, jql: str, fields: str = "key,summary,issuetype,status,created,resolutiondate"):  # noqa: D401
        data = self.get_json("/rest/api/3/search", params={"jql": jql, "fields": fields, "maxResults": 100})
        return data.get("issues", [])

    def search_issues_all(self, jql: str, max_results: int = 500):  # noqa: D401
        """Fetch issues with all fields using pagination (limited to max_results)."""
        issues: List[Dict[str, Any]] = []
        start_at = 0
        while len(issues) < max_results:
            remaining = max_results - len(issues)
            batch_size = min(remaining, 100)
            data = self.get_json(
                "/rest/api/3/search",
                params={"jql": jql, "fields": "*all", "startAt": start_at, "maxResults": batch_size},
            )
            batch = data.get("issues", [])
            if not batch:
                break
            issues.extend(batch)
            total = data.get("total", 0)
            if start_at + batch_size >= total:
                break
            start_at += batch_size
        return issues[:max_results]

    def get_projects(self) -> List[Dict[str, Any]]:  # noqa: D401
        return self.get_json("/rest/api/3/project")

    def get_boards(self, project_key_or_id: Optional[str] = None, board_type: Optional[str] = None) -> Dict[str, Any]:  # noqa: D401
        params: Dict[str, Any] = {}
        if project_key_or_id:
            params["projectKeyOrId"] = project_key_or_id
        if board_type:
            params["type"] = board_type
        return self.get_json("/rest/agile/1.0/board", params=params)

    def get_sprints(self, board_id: int, state: str = "active,future,closed", max_results: int = 50, start_at: int = 0) -> Dict[str, Any]:  # noqa: D401,E501
        params = {"state": state, "maxResults": max_results, "startAt": start_at}
        return self.get_json(f"/rest/agile/1.0/board/{board_id}/sprint", params=params)

    def get_sprint_report(self, board_id: int, sprint_id: int) -> Dict[str, Any]:  # noqa: D401
        return self.get_json(f"/rest/agile/1.0/board/{board_id}/sprint/{sprint_id}/report")

    def get_issue(self, issue_key: str, fields: Optional[str] = None, expand: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:  # noqa: D401,E501
        params: Dict[str, Any] = {} if extra is None else dict(extra)
        if fields:
            params['fields'] = fields
        if expand:
            params['expand'] = expand
        return self.get_json(f"/rest/api/3/issue/{issue_key}", params=params or None)

    def get_issue_changelog(self, issue_key: str, fields: Optional[str] = None) -> Dict[str, Any]:  # noqa: D401
        return self.get_issue(issue_key, fields=fields, expand="changelog")

    def get_issue_worklog(self, issue_key: str) -> Dict[str, Any]:  # noqa: D401
        return self.get_json(f"/rest/api/3/issue/{issue_key}/worklog")
