"""Application configuration loaded from environment variables (.env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseSettings, Field, validator
from dotenv import load_dotenv

# Load .env automatically if present
load_dotenv()

class CoreSettings(BaseSettings):
    app_name: str = Field("ScrumKitchenMetrics", alias="APP_NAME")
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("text", alias="LOG_FORMAT")  # text | json
    timezone: str = Field("UTC", alias="TIMEZONE")

    class Config:
        extra = "ignore"

class JiraSettings(BaseSettings):
    enabled: bool = Field(False, alias="JIRA_ENABLED")
    base_url: Optional[str] = Field(None, alias="JIRA_BASE_URL")
    api_token: Optional[str] = Field(None, alias="JIRA_API_TOKEN")
    user_email: Optional[str] = Field(None, alias="JIRA_USER_EMAIL")
    jql_filter: str = Field("", alias="JIRA_JQL_FILTER")
    verify_ssl: bool = Field(True, alias="JIRA_VERIFY_SSL")

    @validator("base_url", pre=True)
    def strip_slash(cls, v):  # noqa: D401
        if isinstance(v, str):
            return v.rstrip('/')
        return v

    class Config:
        extra = "ignore"

class GitLabSettings(BaseSettings):
    enabled: bool = Field(False, alias="GITLAB_ENABLED")
    base_url: Optional[str] = Field(None, alias="GITLAB_BASE_URL")
    private_token: Optional[str] = Field(None, alias="GITLAB_PRIVATE_TOKEN")
    project_ids: List[int] = Field(default_factory=list, alias="GITLAB_PROJECT_IDS")
    verify_ssl: bool = Field(True, alias="GITLAB_VERIFY_SSL")

    @validator("project_ids", pre=True)
    def parse_ids(cls, v):  # noqa: D401
        if not v:
            return []
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v

    @validator("base_url", pre=True)
    def strip_slash(cls, v):  # noqa: D401
        if isinstance(v, str):
            return v.rstrip('/')
        return v

    class Config:
        extra = "ignore"

class ReportSettings(BaseSettings):
    output_dir: Path = Field(Path("reports"), alias="REPORT_OUTPUT_DIR")
    formats: List[str] = Field(default_factory=lambda: ["PDF", "XLSX"], alias="REPORT_FORMATS")
    template_dir: Path = Field(Path("templates"), alias="TEMPLATE_DIR")
    template_name: str = Field("summary.html.j2", alias="REPORT_TEMPLATE")
    pdf_engine: str = Field("reportlab", alias="REPORT_PDF_ENGINE")  # reportlab | weasyprint

    @validator("formats", pre=True)
    def split_formats(cls, v):  # noqa: D401
        if isinstance(v, str):
            return [x.strip().upper() for x in v.split(',') if x.strip()]
        return v

    class Config:
        extra = "ignore"

class EmailSettings(BaseSettings):
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

    @validator("to", pre=True)
    def parse_recipients(cls, v):  # noqa: D401
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v

    class Config:
        extra = "ignore"

class SchedulerSettings(BaseSettings):
    enabled: bool = Field(False, alias="SCHEDULER_ENABLED")
    cron: str = Field("0 8 * * 1-5", alias="SCHEDULER_CRON")

    class Config:
        extra = "ignore"

class NetworkSettings(BaseSettings):
    http_timeout: int = Field(30, alias="HTTP_TIMEOUT")
    http_retries: int = Field(3, alias="HTTP_RETRIES")
    proxy_url: Optional[str] = Field(None, alias="PROXY_URL")
    cache_enabled: bool = Field(False, alias="CACHE_ENABLED")
    cache_ttl: int = Field(300, alias="CACHE_TTL")
    cache_dir: Path = Field(Path(".api_cache"), alias="CACHE_DIR")

    class Config:
        extra = "ignore"

class FeatureFlags(BaseSettings):
    include_cycle_time: bool = Field(True, alias="FEATURE_INCLUDE_CYCLE_TIME")
    include_bug_ratio: bool = Field(True, alias="FEATURE_INCLUDE_BUG_RATIO")
    include_deploy_frequency: bool = Field(True, alias="FEATURE_INCLUDE_DEPLOY_FREQUENCY")
    plugins_enabled: bool = Field(False, alias="PLUGINS_ENABLED")

class APIServerSettings(BaseSettings):
    host: str = Field("0.0.0.0", alias="API_HOST")
    port: int = Field(8000, alias="API_PORT")
    enabled: bool = Field(False, alias="API_ENABLED")

    class Config:
        extra = "ignore"

class Settings(BaseSettings):
    core: CoreSettings = CoreSettings()
    jira: JiraSettings = JiraSettings()
    gitlab: GitLabSettings = GitLabSettings()
    report: ReportSettings = ReportSettings()
    email: EmailSettings = EmailSettings()
    scheduler: SchedulerSettings = SchedulerSettings()
    network: NetworkSettings = NetworkSettings()
    features: FeatureFlags = FeatureFlags()
    api: APIServerSettings = APIServerSettings()

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[arg-type]
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
]
