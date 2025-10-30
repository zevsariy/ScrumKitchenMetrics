# ScrumKitchenMetrics

Гибкий фреймворк на Python для получения данных из внешних систем (JIRA, GitLab и др.), расчёта продуктовых / инженерных метрик и формирования отчётов в форматах PDF и XLSX с последующей отправкой по email (Gmail или Exchange).

## Ключевые возможности

- Поддержка JIRA REST API (по JQL фильтрам)
- Поддержка GitLab API (через библиотеку `python-gitlab`)
- Лёгкое добавление новых источников (единая абстракция клиентов)
- Архитектура метрик с простым расширением (каждая метрика — класс)
- Рендеринг HTML отчёта через Jinja2 и экспорт в PDF / XLSX (движки ReportLab / WeasyPrint)
- Отправка email через Gmail (SMTP + App Password) или Exchange / Office365
- Включение / отключение функционала через переменные окружения (feature flags)
- CLI интерфейс (`skm`) для основных операций и планировщика
- Опциональный FastAPI сервер (/health, /metrics, /report)
- Кэширование ответов API (diskcache) — включается флагом
- Система плагинов (pluggy entry points) для внешних метрик (экспериментально)
- Все настройки через `.env` (есть пример `.env.example`)

## Стек

`Python 3.11+`, `pydantic`, `httpx`, `python-dotenv`, `jinja2`, `reportlab`, `openpyxl`, `typer`, `rich`, `python-gitlab`.

## Установка и запуск (локально)

1. Склонируйте репозиторий:
	```bash
	git clone https://github.com/<your-org>/ScrumKitchenMetrics.git
	cd ScrumKitchenMetrics
	```
2. Создайте и активируйте виртуальное окружение (пример для Windows PowerShell):
	```powershell
	python -m venv .venv; .venv\Scripts\Activate.ps1
	```
3. Установите зависимости:
	```powershell
	pip install -e .[dev]
	```
4. Скопируйте файл настроек и заполните секреты:
	```powershell
	copy .env.example .env
	# Отредактируйте .env
	```
5. Подготовьте хотя бы один Jinja2 шаблон:
	```
	templates/summary.html.j2
	```
	Пример минимального шаблона:
	```html
	<html><body>
	<h2>{{ app_name }} Metrics ({{ generated_at }})</h2>
	<table border="1" cellspacing="0" cellpadding="4">
	  <tr><th>Key</th><th>Label</th><th>Value</th><th>Description</th></tr>
	  {% for m in metrics %}
		 <tr>
			<td>{{ m.key }}</td>
			<td>{{ m.label }}</td>
			<td>{{ m.value }}</td>
			<td>{{ m.description }}</td>
		 </tr>
	  {% endfor %}
	</table>
	</body></html>
	```

## Переменные окружения (основные)

Смотрите полный список в `.env.example`.

| Группа | Переменная | Назначение |
|--------|------------|-----------|
| CORE | APP_NAME | Имя приложения |
| JIRA | JIRA_BASE_URL, JIRA_API_TOKEN, JIRA_USER_EMAIL | Настройки доступа к JIRA |
| GITLAB | GITLAB_BASE_URL, GITLAB_PRIVATE_TOKEN, GITLAB_PROJECT_IDS | Настройки GitLab |
| REPORT | REPORT_FORMATS, REPORT_OUTPUT_DIR | Форматы и директория отчетов |
| EMAIL | EMAIL_PROVIDER, EMAIL_TO, EMAIL_FROM | Отправка писем |
| FEATURE | FEATURE_INCLUDE_* | Feature flags |

## CLI команды

После установки скрипт доступен как `skm`:

```powershell
skm fetch-metrics --json-output        # Получить метрики (JSON)
skm generate_report                    # Сгенерировать отчеты (PDF/XLSX)
skm send_report                        # Отправить последний отчет по email
skm run_all                            # Полный цикл: собрать -> отчет -> отправить
skm start_scheduler                    # Запуск APScheduler по SCHEDULER_CRON
```

## FastAPI сервер

Включается `API_ENABLED=true` (плюс установлены зависимости). Запуск:

```powershell
uvicorn scrum_kitchen_metrics.api_server:app --host 0.0.0.0 --port 8000
```

Эндпоинты:
- `GET /health`
- `GET /metrics`
- `POST /report` (генерирует файлы и возвращает список путей)

## Кэширование API

Включите `CACHE_ENABLED=true`, настройте `CACHE_TTL` и `CACHE_DIR`. Кэш работает только для GET запросов.

## PDF движок

`REPORT_PDF_ENGINE=weasyprint` для улучшенной верстки (требует системные зависимости WeasyPrint). Иначе используется простой fallback.

## Структурированные логи

`LOG_FORMAT=json` переключает формат логов на JSON.

## Плагины метрик

При `PLUGINS_ENABLED=true` можно публиковать пакет с entry point:

```toml
[project.entry-points."skm"]
my_extra_metrics = "my_package.metrics:register"
```

Функция `register` должна вернуть iterable классов метрик.

## Добавление новой метрики

1. Создайте класс в `metrics/` унаследованный от `Metric`.
2. Реализуйте метод `compute()` возвращающий `MetricResult`.
3. Зарегистрируйте класс в списке `METRIC_CLASSES` в `cli.py` (или создайте механизм авто-дискавери — см. раздел «Расширения» ниже).

## Добавление нового API клиента

1. Создайте класс наследник `BaseAPIClient` (если HTTP) в `api/`.
2. Реализуйте `auth_headers()` и методы для необходимых эндпоинтов.
3. Используйте его внутри новых метрик.

## Безопасность

Файл `.env` добавлен в `.gitignore` и не должен коммититься. Для production используйте переменные окружения CI/CD или Secret Manager.

## Тесты

```powershell
pytest -q
```

## Планируемые улучшения / расширения

- Авто-дискавери метрик (entry points / динамический импорт)
- Кэширование ответов API (например, sqlite + hash запроса)
- Более качественный HTML->PDF (WeasyPrint / wkhtmltopdf)
- Система плагинов для дополнительных источников (Azure DevOps, Jenkins и т.п.)
- REST API / FastAPI над тем же ядром
- Dockerfile и Helm chart

## Лицензия

MIT License (см. `LICENSE`).

---
Будут вопросы или нужны доработки — добавляйте issue / PR.