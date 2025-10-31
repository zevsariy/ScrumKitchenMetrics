"""JIRA sprint-focused metric stubs (T2M, Lead Time, Spillover, Plan/Fact, Summary)."""
from __future__ import annotations

from ..config import get_settings
from ..services.jira_sprint_metrics import JiraSprintMetricsService
from .base import Metric, MetricResult

class _BaseJiraSprintMetric(Metric):
    source = 'jira'

    def _service(self) -> JiraSprintMetricsService:
        return JiraSprintMetricsService()

    def _disabled_result(self) -> MetricResult:
        return MetricResult(self.key, self.label, None, "JIRA отключена или не настроены доски", {'note': 'JIRA disabled'})

class JiraSprintTimeToMarketMetric(_BaseJiraSprintMetric):
    key = 'jira_t2m'
    label = 'JIRA Time-to-Market (заготовка)'
    description = 'Средняя длительность спринта как приближённое значение T2M за последние N спринтов.'

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not (settings.enabled and settings.board_ids):
            return self._disabled_result()
        data = self._service().compute_time_to_market()
        return MetricResult(self.key, self.label, data['value'], data.get('note'), data)

class JiraSprintLeadTimeDeliveryMetric(_BaseJiraSprintMetric):
    key = 'jira_lead_time_delivery'
    label = 'Lead Time (Delivery) заготовка'
    description = 'Шаблон метрики Lead Time по delivery стадиям, адаптируйте под реальные статусы.'

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not (settings.enabled and settings.board_ids):
            return self._disabled_result()
        data = self._service().compute_lead_time_delivery()
        return MetricResult(self.key, self.label, data['value'], data.get('note'), data)

class JiraSprintLeadTimeDiscoveryMetric(_BaseJiraSprintMetric):
    key = 'jira_lead_time_discovery'
    label = 'Lead Time (Discovery) заготовка'
    description = 'Требует настроить статусы discovery и анализ changelog, по умолчанию возвращает None.'

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not (settings.enabled and settings.board_ids):
            return self._disabled_result()
        data = self._service().compute_lead_time_discovery()
        return MetricResult(self.key, self.label, data['value'], data.get('note'), data)

class JiraSprintSpilloverMetric(_BaseJiraSprintMetric):
    key = 'jira_spillover_ratio'
    label = 'Spillover Ratio'
    description = 'Доля незавершённых задач от плана в последних спринтах.'

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not (settings.enabled and settings.board_ids):
            return self._disabled_result()
        data = self._service().compute_spillover()
        return MetricResult(self.key, self.label, data['value'], data.get('note'), data)

class JiraSprintPlanFactMetric(_BaseJiraSprintMetric):
    key = 'jira_sprint_plan_fact'
    label = 'Sprint Plan vs Fact'
    description = 'Сводка по плану/факту задач и story points.'

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not (settings.enabled and settings.board_ids):
            return self._disabled_result()
        data = self._service().compute_plan_vs_fact()
        return MetricResult(self.key, self.label, data['value'], data.get('note'), data)

class JiraSprintVelocityTrendMetric(_BaseJiraSprintMetric):
    key = 'jira_velocity_trend'
    label = 'Velocity Trend'
    description = 'Заготовка для графика velocity по завершённым story points.'

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not (settings.enabled and settings.board_ids):
            return self._disabled_result()
        data = self._service().compute_velocity_trend()
        return MetricResult(self.key, self.label, data['value'], data.get('note'), data)

class JiraSprintOverviewMetric(_BaseJiraSprintMetric):
    key = 'jira_sprint_overview'
    label = 'Sprint Overview'
    description = 'Суммарный отчёт по последним спринтам (кол-во, краткая сводка).'

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not (settings.enabled and settings.board_ids):
            return self._disabled_result()
        data = self._service().compute_sprint_overview()
        return MetricResult(self.key, self.label, data['value'], data.get('note'), data)

class JiraSprintTeamProgressMetric(_BaseJiraSprintMetric):
    key = 'jira_team_progress'
    label = 'Sprint Team Progress'
    description = 'Разбивка спринтов по командам: план/факт, story points, списанные часы.'

    def compute(self) -> MetricResult:  # noqa: D401
        settings = get_settings().jira
        if not (settings.enabled and settings.board_ids):
            return self._disabled_result()
        data = self._service().compute_team_breakdown()
        return MetricResult(self.key, self.label, data['value'], data.get('note'), data)

__all__ = [
    'JiraSprintTimeToMarketMetric',
    'JiraSprintLeadTimeDeliveryMetric',
    'JiraSprintLeadTimeDiscoveryMetric',
    'JiraSprintSpilloverMetric',
    'JiraSprintPlanFactMetric',
    'JiraSprintVelocityTrendMetric',
    'JiraSprintOverviewMetric',
    'JiraSprintTeamProgressMetric',
]
