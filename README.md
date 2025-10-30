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

### Формат GITLAB_PROJECT_IDS

В pydantic-settings для полей типа список предпочтителен JSON формат. Поэтому в `.env` используйте:

```env
GITLAB_PROJECT_IDS=[12345,67890]
```

Если хотите поддержать простой CSV, можно изменить валидатор в `GitLabSettings` (сейчас ожидается JSON массив). Либо временно поменять тип поля на `str` и распарсить вручную.

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

## Встроенный UI (локальное использование)

Локальный веб UI доступен по адресу `http://127.0.0.1:8000/ui` (при запущенном сервере FastAPI).

Функции UI:
1. Dashboard: быстрый снимок метрик, последние файлы отчётов, кнопки Generate/Send.
2. Metrics: включение/отключение метрик (под капотом обновляется `overrides.env` ключ `DISABLED_METRICS`).
3. Custom Metrics: на той же странице `Metrics` можно добавлять динамические метрики без изменения кода. Укажите `key`, `label`, `expression` (безопасный подмножество Python: len, sum, min, max, round + переменные), и описание. Метрика сохраняется в `custom_metrics.json` и немедленно регистрируется.
4. Report Editor: страница `Report` позволяет редактировать Jinja2 шаблон отчёта прямо из браузера, а также изменять список форматов (`REPORT_FORMATS`) и PDF движок (`REPORT_PDF_ENGINE`). После сохранения обновляется файл шаблона и `overrides.env`.
5. Config: редактирование подмножества настроек (JIRA_ENABLED, GITLAB_ENABLED, REPORT_FORMATS, EMAIL_* , LOG_*) через форму.

Механизм overrides:
- Файл `overrides.env` (игнорируется Git) накладывается поверх `.env` и может изменяться через UI.
- После сохранения происходит очистка кэша настроек.

Ограничения первой версии:
- Секреты (токены, пароли) не редактируются через UI.
- Для постоянных изменений всё равно рекомендуется обновлять `.env` вручную.
- Авторизация не реализована (UI предназначен для локального запуска).
 - В выражениях кастомных метрик запрещены любые небезопасные имена; доступен только whitelisted набор.
 - Для сложных вычислений лучше добавить полноценный класс метрики в кодовой базе.

Запуск и доступ:
```powershell
uvicorn scrum_kitchen_metrics.api_server:app --reload
# затем открыть http://127.0.0.1:8000/ui
```

Авто-открытие браузера: при запуске через `python main.py server` интерфейс автоматически открывается в системном браузере (можно отключить удалив вызов `webbrowser.open` из `main.py`).

## Кэширование API

Включите `CACHE_ENABLED=true`, настройте `CACHE_TTL` и `CACHE_DIR`. Кэш работает только для GET запросов.

## PDF движок

`REPORT_PDF_ENGINE=weasyprint` для улучшенной верстки (требует системные зависимости WeasyPrint). Иначе используется простой fallback.

### WeasyPrint (опционально) и Windows

При установке `weasyprint` на Windows могут появиться ошибки сборки пакетов `brotli` или `zopfli` (часть зависимости `fonttools[woff]`), если не установлены инструменты сборки C++. Варианты:

1. Быстрый старт без WeasyPrint (рекомендуется):
	```powershell
	pip install -r requirements-min.txt
	# В .env установите REPORT_PDF_ENGINE=reportlab или просто не указывайте переменную
	```
2. Установка с WeasyPrint (требует Microsoft C++ Build Tools):
	- Скачайте и установите: https://visualstudio.microsoft.com/visual-cpp-build-tools/
	- Во время установки отметьте «Desktop development with C++» или минимум компоненты Windows 10/11 SDK и MSVC.
	- После установки перезапустите терминал и выполните:
	  ```powershell
	  pip install -r requirements.txt
	  ```
3. Альтернативно можно использовать предварительно собранные бинарные пакеты (когда появятся для вашей версии Python) — тогда сборка проходить не будет.

Если WeasyPrint не установлен или падает при генерации PDF, код автоматически сделает fallback на простой текстовый PDF через ReportLab.

Рекомендация по версии Python: используйте 3.11 или 3.12 для лучшей совместимости бинарных колёс. Слишком новые версии (например, только что вышедшие 3.14) могут временно не иметь готовых wheels и вызывать сборку из исходников.

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

Добавлен тест `test_custom_metric_ui.py`, проверяющий добавление кастомной метрики через UI и её вычисление.

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
## Примечания о времени / таймзоне

Все временные метки теперь формируются через `datetime.now(datetime.UTC)` (Python 3.11+) вместо устаревшего `datetime.utcnow()` чтобы избегать предупреждений о депрекации и явно фиксировать часовой пояс UTC.

---
Будут вопросы или нужны доработки — добавляйте issue / PR.

---
## Быстрый упрощённый запуск (без установки пакета)

Если не хотите работать через `pip install -e .` и `pyproject.toml`, можно использовать только `requirements.txt` и скрипт `main.py`.

1. Создайте (или очистите) виртуальное окружение:
	```powershell
	python -m venv .venv; . .\.venv\Scripts\Activate.ps1
	```
2. Установите зависимости:
	```powershell
	pip install -r requirements.txt
	```
3. Скопируйте пример окружения:
	```powershell
	if (-not (Test-Path .env)) { Copy-Item .env.example .env }
	```
4. Запустите сервер:
	```powershell
	python main.py server --reload
	```
	UI: http://127.0.0.1:8000/ui
5. Посмотреть метрики:
	```powershell
	python main.py metrics
	```
6. Сгенерировать отчёт:
	```powershell
	python main.py report --name first_report
	```

### Минимальная установка (без WeasyPrint)

Если нужен только базовый PDF (ReportLab):
```powershell
pip install -r requirements-min.txt
```
`REPORT_PDF_ENGINE` можно оставить пустым или указать `reportlab`.

Чтобы позже добавить WeasyPrint:
```powershell
pip install weasyprint fonttools brotli zopfli
setx REPORT_PDF_ENGINE weasyprint  # или добавьте в .env
```

Этот способ не регистрирует entrypoint скрипты, но подходит для локального быстрого прогона.