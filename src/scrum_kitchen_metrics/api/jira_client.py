"""Minimal JIRA client for needed endpoints."""
from __future__ import annotations

from typing import Any, Dict, List

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
        data = self.get_json("/rest/api/3/search", params={"jql": jql, "fields": fields, "maxResults": 1000})
        return data.get("issues", [])

    def get_projects(self) -> List[Dict[str, Any]]:  # noqa: D401
        return self.get_json("/rest/api/3/project")
