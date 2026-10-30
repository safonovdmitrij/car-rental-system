# Логування: інфраструктурні тести та RED

Дата: 30.10.2026. Виконавець: Codex. База: `f807c66` — backend-середовище закомічено користувачем. Початковий `git status --short` порожній, гілка main. Чинні [рішення підготовки](../preparation-decisions.md), [план §8](../../../../planning/tdd-implementation-plan.md), [інструкція середовища](../../../../docs/backend-setup.md) і конвенція комітів прочитані. AGENTS.md пошуком не знайдено. Дозвіл цього етапу — нове повідомлення користувача: написати тести та зафіксувати RED, без реалізації логування. Сторонніх змін не виявлено; add/commit/push не виконувалися.

## Що підготовлено

[test_logging.py](../../../../tests/infrastructure/test_logging.py) містить 9 інфраструктурних випадків. Джерела очікувань — явне завдання користувача, погоджене JSON-логування/request_id та §8 плану; вони не оголошуються календарними REQ/AC/BDD або бізнес-контрактними тестами. Назви внутрішніх полів `time`, `event`, `result`, `request_id`, `status`, `duration_ms` — тестований внутрішній формат журналу, не нові HTTP-поля.

[observability.py](../../../../src/car_rental/observability.py) містить лише інтерфейси JsonEventLogger, RequestLoggingMiddleware, current_request_id та record_test_run. Конструктори зберігають передані залежності; у всіх цільових операціях явний NotImplementedError. Серіалізації, фільтрації полів, генерації id, ASGI-обробки, контексту чи запису журналів немає. У робочий застосунок middleware не підключено. Мінімальні bare-ASGI callables існують лише всередині тестів; маршрути/обов’язкові заголовки/поля API не додаються, main.py та OpenAPI незмінні.

Дані виключно синтетичні. Приватні canary-значення не повинні потрапляти навіть у помилки журналу. Тести використовують StringIO або pytest tmp_path; не читають робочу БД чи локальні секрети. HTTPX ASGITransport працює в процесі без сервера/сокета.

## Перевірки до RED

Точні аргументи всіх команд, час UTC, версії, hashes і exit code — у [manifest.json](manifest.json). Використано Python 3.14.0, pip 25.2, pytest 9.2.0, FastAPI 0.162.0, HTTPX 0.28.1, Starlette 1.10.0; версію AnyIO також зафіксовано в manifest. Залежності не змінювалися.

| Контроль | Фактичний результат / аналіз журналу |
| --- | --- |
| pip check | Exit 0; [dependencies.txt](dependencies.txt): несумісних залежностей немає |
| Окремі імпорти чотирьох нових інтерфейсів | Exit 0; [imports.txt](imports.txt): імпорти працюють незалежно від бізнес-поведінки |
| pytest на test_environment.py | Exit 0, 3 PASS; [runner.txt](runner.txt): runner, HTTPX/ASGI та середовище працюють, попереджень немає |
| collect-only test_logging.py | Exit 0, 9 test ID; [collect.txt](collect.txt): всі потрібні випадки зібрано, помилок синтаксису/імпорту немає |
| Нові тести | Exit 1, 9 FAIL, 0 ERROR/SKIP; [red.txt](red.txt), [red.xml](red.xml). Exit відповідає очікуваному RED, не збою runner |

Для всіх pytest-команд вимкнено cacheprovider, задано локальний `--basetemp=.backend-setup/logging-pytest-temp`, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1; це запобігає залежності від сторонніх plugin/cache/system-temp. Тимчасові файли ігноруються Git. Тестові stdout/stderr перед збереженням перевірені на canary-значення. У JUnit hostname замінено на `local`; test ID, результат і текст причин не змінені.

Команда RED з кореня репозиторію (PowerShell):

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONPATH = 'src'
.\.venv-backend\Scripts\python.exe -m pytest tests/infrastructure/test_logging.py -q --tb=short --assert=plain --show-capture=no --junitxml=logs/tdd/T01/logging-red/red.xml -p no:cacheprovider --basetemp=.backend-setup/logging-pytest-temp
```

Команда наведена точно як у фактичному запуску. Для наступного контрольного запуску вказати **новий** шлях JUnit та доказів, не перезаписувати цю RED-базу. Після процесу негайно зберегти `$LASTEXITCODE`, перевірити відповідність JUnit й безпечність результатів. Assertion rewriting/locals/captured bodies не вмикати для передачі артефактів із sensitive-canary тестів.

## Причини кожного падіння

Повний префікс кожного test ID: `tests/infrastructure/test_logging.py::`.

| Test ID (суфікс) | Очікування та фактична причина RED |
| --- | --- |
| test_json_event_has_utc_time_type_result_and_request_id | Одна валідна JSON-подія з UTC-часом, типом, результатом і заданим request_id. emit піднімає NotImplementedError, подія не записана |
| test_event_allowlist_excludes_sensitive_fields_even_on_error[success] | Безпечна подія без body/password/authorization/контактів/сирого винятку/довільного поля. emit піднімає NotImplementedError до серіалізації/фільтрації |
| test_event_allowlist_excludes_sensitive_fields_even_on_error[error] | Така сама allowlist-вимога при error. emit піднімає NotImplementedError; error-подія також не реалізована |
| test_http_start_end_status_duration_and_correlation[success] | Делегувати запит тестовому ASGI-app, зберегти 204, створити start/end з одним id, статусом і скінченною невід’ємною тривалістю. Заглушка middleware не викликає app; HTTPX із raise_app_exceptions=False перетворює NotImplementedError на 500, тому assertion статусу падає |
| test_http_start_end_status_duration_and_correlation[error] | За винятку app — start/end, завершення зі status=500/result=error і кореляцією. HTTPX дає 500 вже від заглушки middleware, але журнал порожній; перевірка обов’язкових start/end падає |
| test_concurrent_requests_correlate_operation_events_without_context_leak | Для двох переплетених запитів — два різні id, по start/operation/end на кожний. Middleware піднімає NotImplementedError, що прямо виходить через HTTPX; ні request context, ні кореляція ще не існують |
| test_http_error_does_not_log_body_credentials_contacts_or_exception_text | Обов’язкові error-події без тіла, Authorization, контактів, query та сирого тексту винятку. Порожній stream через заглушку: перевірка start/end падає до privacy-assertions. Порожній журнал не зараховується доказом приватності |
| test_test_run_journal_records_exact_command_exit_code_and_result[0-PASS] | Окремий JSONL-журнал із точною командою як argv, run_id, UTC-часом, exit=0/result=PASS. record_test_run піднімає NotImplementedError, файл не записано |
| test_test_run_journal_records_exact_command_exit_code_and_result[1-FAIL] | Таке саме збереження exit=1/result=FAIL, без підміни невдалого результату успіхом. record_test_run піднімає NotImplementedError, файл не записано |

Це справжній запуск тестів проти відсутньої поведінки, а не тести, які очікують NotImplementedError. Жоден тест не asserts заглушку, не skip/xfail. Конструктори та імпорти працюють; tmp_path і runner справні. Винятки заглушок прямо видимі для emit/concurrency/run-journal та пояснюють HTTPX-500/порожній stream в інших випадках. Усі дев’ять падінь мають предметну причину; помилок оточення, імпорту, фікстур чи кешу під час цих запусків немає.

## Безпека доказів та межі результату

Перевірено текст кожного stdout/stderr після запуску. Журнали містять лише test ID, безпечні статичні повідомлення заглушок і рядки assertions без значень. У JUnit немає request bodies, паролів, токенів, контактів або hostname робочої машини. Додатковий автоматичний скан перевіряє canary-значення, email-подібні контакти й локальні персональні шляхи; source hashes та результати JUnit звіряються окремо. Файли тестів містять лише синтетичні маркери для майбутньої перевірки; реальних секретів у них немає. Кеш, віртуальне середовище та тимчасові файли не включаються в передачу.

Наявні докази отримано одноразовою зовнішньою оркестрацією subprocess, а не цільовим record_test_run; наявність manifest не означає, що функція журналювання вже реалізована. [actions.jsonl](actions.jsonl) — журнал дій агента цього етапу, не результат роботи майбутнього API-логера. Перевірки безпеки доказів не є GREEN для приватності API.

Результат — **інфраструктурний RED**, не TEST-GATE/G-READY, Validation, календарний RED або перевірка OP-09/10. Майбутній GREEN повинен виконати всі assertions; зараз privacy, реальна кореляція/тривалість, запис журналу запусків залишаються непідтвердженими. Production sinks/rotation, streaming/disconnect/non-HTTP ASGI та подальші бізнес-події цим малим набором не перевіряються. Нічого з цього не оголошено реалізованим. Календарний код і контракт не змінені.

Зупинка після RED для людського перегляду й окремого коміту. Мінімальна реалізація логування можлива лише після повідомлення користувача про коміт тестів та доказів і наступного доручення. Рекомендована назва: `test: specify logging behavior and capture infrastructure RED`.
