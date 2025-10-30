"""Application configuration loaded from environment variables (.env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import os
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

# Load base .env then overrides.env if exists
load_dotenv(dotenv_path=Path('.env'), override=False)
if Path('overrides.env').exists():
    load_dotenv(dotenv_path=Path('overrides.env'), override=True)

class EnvModel(BaseModel):
    """Base model with helper to construct from environment variables using field aliases.

    Performs light type coercion:
      - bool fields: recognize true/false/on/off/1/0 (case-insensitive)
      - int fields: parse int
      - list[str]/list[int]: accept JSON array or comma-separated values
      - Path fields: create Path
    """

    @classmethod
    def from_env(cls):  # noqa: D401
        data = {}
        for name, field in cls.model_fields.items():  # type: ignore[attr-defined]
            env_name = field.alias or name
            if env_name not in os.environ:
                continue
            raw = os.environ[env_name]
            target_type = field.annotation
            value = raw
            try:
                origin = getattr(target_type, '__origin__', None)
                if target_type is bool:
                    lowered = raw.lower()
                    value = lowered in {'true', '1', 'on', 'yes', 'y'}
                elif target_type is int:
                    value = int(raw)
                elif target_type is Path:
                    value = Path(raw)
                elif origin is list or (str(target_type).startswith('typing.List') or str(target_type).startswith('list[')):
                    args = getattr(target_type, '__args__', [])
                    inner = args[0] if args else str
                    txt = raw.strip()
                    if txt.startswith('[') and txt.endswith(']'):
                        import json
                        try:
                            arr = json.loads(txt)
                        except Exception:  # noqa: BLE001
                            arr = []
                        if not isinstance(arr, list):
                            arr = []
                        items = arr
                    else:
                        items = [x.strip() for x in txt.split(',') if x.strip()]
                    coerced = []
                    for it in items:
                        if inner is int:
                            try:
                                coerced.append(int(it))
                            except Exception:  # noqa: BLE001
                                continue
                        else:
                            coerced.append(str(it))
                    value = coerced
            except Exception:  # noqa: BLE001
                value = raw
            # Populate by alias and field name for robustness
            if field.alias:
                data[field.alias] = value
            data[name] = value
        return cls.model_validate(data)

    model_config = {"extra": "ignore"}


class CoreSettings(EnvModel):
    app_name: str = Field("ScrumKitchenMetrics", alias="APP_NAME")
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("text", alias="LOG_FORMAT")  # text | json
    timezone: str = Field("UTC", alias="TIMEZONE")

    model_config = {"extra": "ignore"}

class JiraSettings(EnvModel):
    enabled: bool = Field(False, alias="JIRA_ENABLED")
    base_url: Optional[str] = Field(None, alias="JIRA_BASE_URL")
    api_token: Optional[str] = Field(None, alias="JIRA_API_TOKEN")
    user_email: Optional[str] = Field(None, alias="JIRA_USER_EMAIL")
    jql_filter: str = Field("", alias="JIRA_JQL_FILTER")
    verify_ssl: bool = Field(True, alias="JIRA_VERIFY_SSL")

    @field_validator("base_url", mode="before")
    def strip_slash(cls, v):  # noqa: D401
        if isinstance(v, str):
            return v.rstrip('/')
        return v

    model_config = {"extra": "ignore"}

class GitLabSettings(EnvModel):
    enabled: bool = Field(False, alias="GITLAB_ENABLED")
    base_url: Optional[str] = Field(None, alias="GITLAB_BASE_URL")
    private_token: Optional[str] = Field(None, alias="GITLAB_PRIVATE_TOKEN")
    verify_ssl: bool = Field(True, alias="GITLAB_VERIFY_SSL")
    project_ids: List[int] = Field(default_factory=list, alias="GITLAB_PROJECT_IDS")

    @field_validator("project_ids", mode="before")
    def parse_project_ids(cls, v):  # noqa: D401
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            txt = v.strip()
            if txt.startswith('[') and txt.endswith(']'):
                import json
                try:
                    arr = json.loads(txt)
                    if isinstance(arr, list):
                        return [int(x) for x in arr]
                except Exception:  # noqa: BLE001
                    return []
            return [int(x.strip()) for x in txt.split(',') if x.strip()]
        return []

    @field_validator("base_url", mode="before")
    def strip_slash(cls, v):  # noqa: D401
        if isinstance(v, str):
            return v.rstrip('/')
        return v

    model_config = {"extra": "ignore"}

class ReportSettings(EnvModel):
    output_dir: Path = Field(Path("reports"), alias="REPORT_OUTPUT_DIR")
    formats: List[str] = Field(default_factory=lambda: ["PDF", "XLSX"], alias="REPORT_FORMATS")
    template_dir: Path = Field(Path("templates"), alias="TEMPLATE_DIR")
    template_name: str = Field("summary.html.j2", alias="REPORT_TEMPLATE")
    pdf_engine: str = Field("reportlab", alias="REPORT_PDF_ENGINE")  # reportlab | weasyprint

    @field_validator("formats", mode="before")
    def split_formats(cls, v):  # noqa: D401
        if isinstance(v, str):
            return [x.strip().upper() for x in v.split(',') if x.strip()]
        return v

    model_config = {"extra": "ignore"}

class EmailSettings(EnvModel):
    enabled: bool = Field(False, alias="EMAIL_ENABLED")
    provider: str = Field("gmail", alias="EMAIL_PROVIDER")  # gmail | exchange
    subject_prefix: str = Field("[Metrics]", alias="EMAIL_SUBJECT_PREFIX")
    send_pdf: bool = Field(True, alias="EMAIL_SEND_PDF")
    send_xlsx: bool = Field(True, alias="EMAIL_SEND_XLSX")
    to: List[str] = Field(default_factory=list, alias="EMAIL_TO")
    from_address: Optional[str] = Field(None, alias="EMAIL_FROM")

    # Gmail
    gmail_server: str = Field("smtp.gmail.com", alias="GMAIL_SMTP_SERVER")
    gmail_port: int = Field(587, alias="GMAIL_SMTP_PORT")
    gmail_user: Optional[str] = Field(None, alias="GMAIL_USER")
    gmail_app_password: Optional[str] = Field(None, alias="GMAIL_APP_PASSWORD")

    # Exchange
    exchange_server: str = Field("smtp.office365.com", alias="EXCHANGE_SMTP_SERVER")
    exchange_port: int = Field(587, alias="EXCHANGE_SMTP_PORT")
    exchange_user: Optional[str] = Field(None, alias="EXCHANGE_USER")
    exchange_password: Optional[str] = Field(None, alias="EXCHANGE_PASSWORD")

    @field_validator("to", mode="before")
    def parse_recipients(cls, v):  # noqa: D401
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v

    model_config = {"extra": "ignore"}

class SchedulerSettings(EnvModel):
    enabled: bool = Field(False, alias="SCHEDULER_ENABLED")
    cron: str = Field("0 8 * * 1-5", alias="SCHEDULER_CRON")

    model_config = {"extra": "ignore"}

class NetworkSettings(EnvModel):
    http_timeout: int = Field(30, alias="HTTP_TIMEOUT")
    http_retries: int = Field(3, alias="HTTP_RETRIES")
    proxy_url: Optional[str] = Field(None, alias="PROXY_URL")
    cache_enabled: bool = Field(False, alias="CACHE_ENABLED")
    cache_ttl: int = Field(300, alias="CACHE_TTL")
    cache_dir: Path = Field(Path(".api_cache"), alias="CACHE_DIR")

    model_config = {"extra": "ignore"}

class FeatureFlags(EnvModel):
    include_cycle_time: bool = Field(True, alias="FEATURE_INCLUDE_CYCLE_TIME")
    include_bug_ratio: bool = Field(True, alias="FEATURE_INCLUDE_BUG_RATIO")
    include_deploy_frequency: bool = Field(True, alias="FEATURE_INCLUDE_DEPLOY_FREQUENCY")
    plugins_enabled: bool = Field(False, alias="PLUGINS_ENABLED")

class APIServerSettings(EnvModel):
    host: str = Field("0.0.0.0", alias="API_HOST")
    port: int = Field(8000, alias="API_PORT")
    enabled: bool = Field(False, alias="API_ENABLED")

    model_config = {"extra": "ignore"}

class Settings(BaseModel):
    core: CoreSettings
    jira: JiraSettings
    gitlab: GitLabSettings
    report: ReportSettings
    email: EmailSettings
    scheduler: SchedulerSettings
    network: NetworkSettings
    features: FeatureFlags
    api: APIServerSettings

    model_config = {"extra": "ignore"}

def _build_settings() -> Settings:
    return Settings(
        core=CoreSettings.from_env(),
        jira=JiraSettings.from_env(),
        gitlab=GitLabSettings.from_env(),
        report=ReportSettings.from_env(),
        email=EmailSettings.from_env(),
        scheduler=SchedulerSettings.from_env(),
        network=NetworkSettings.from_env(),
        features=FeatureFlags.from_env(),
        api=APIServerSettings.from_env(),
    )
@lru_cache()
def get_settings() -> Settings:
    settings = _build_settings()
    # ensure output directories exist
    settings.report.output_dir.mkdir(parents=True, exist_ok=True)
    settings.report.template_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    if settings.jira.enabled:
        if not (settings.jira.base_url and settings.jira.api_token and settings.jira.user_email):
            errors.append("JIRA enabled but JIRA_BASE_URL/JIRA_API_TOKEN/JIRA_USER_EMAIL missing")
    if settings.gitlab.enabled:
        if not (settings.gitlab.base_url and settings.gitlab.private_token):
            errors.append("GITLAB enabled but GITLAB_BASE_URL/GITLAB_PRIVATE_TOKEN missing")
    if settings.email.enabled:
        if settings.email.provider == 'gmail' and not (settings.email.gmail_user and settings.email.gmail_app_password):
            errors.append("Gmail email enabled but GMAIL_USER/GMAIL_APP_PASSWORD missing")
        if settings.email.provider == 'exchange' and not (settings.email.exchange_user and settings.email.exchange_password):
            errors.append("Exchange email enabled but EXCHANGE_USER/EXCHANGE_PASSWORD missing")
    if errors:
        raise ValueError("Configuration validation error(s):\n - " + "\n - ".join(errors))
    return settings

__all__ = [
    "Settings",
    "get_settings",
    "_build_settings",
    "refresh_settings",
]

def refresh_settings() -> Settings:  # noqa: D401
    """Clear cached settings and rebuild."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
    return get_settings()
