# Запуск backend-середовища

Підготовлені ASGI-застосунок, інфраструктурний runner та мінімальне JSON-логування. Бізнес-маршрутів і календарної реалізації ще немає. Рішення про обсяг — [T01 preparation-decisions](../logs/tdd/T01/preparation-decisions.md), історичний setup — [звіт середовища](../logs/tdd/T01/environment/review.md), результати логування — [GREEN-звіт](../logs/tdd/T01/logging-green/review.md).

## Відтворення: Windows x86-64, CPython 3.14.0

`uv` не знайдено; використано стандартні venv і pip. `.python-version` документує Python 3.14.0, але сам не встановлює й не перемикає інтерпретатор. Команди нижче виконуються з кореня репозиторію у PowerShell. Активація середовища не потрібна.

```powershell
python --version
# Перед продовженням перевірити: Python 3.14.0, Windows x86-64.
python -m venv .venv-backend
.\.venv-backend\Scripts\python.exe -m pip --version
# Для відтворення використано pip 25.2 (ensurepip у Python 3.14.0).
.\.venv-backend\Scripts\python.exe -m pip --isolated install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r requirements/backend.lock
.\.venv-backend\Scripts\python.exe -m pip check
```

[backend.in](../requirements/backend.in) описує прямі залежності й межі підбору. **Встановлювати слід [backend.lock](../requirements/backend.lock)**: у ньому всі 30 розв’язаних дистрибутивів мають точні версії та SHA-256 коліс. `psycopg-binary` зафіксований окремо разом із psycopg. Hash checking забезпечується pip `--require-hashes`: [офіційна документація](https://pip.pypa.io/en/stable/topics/repeatable-installs/). Ізоляція venv описана в [документації Python](https://docs.python.org/3.14/library/venv.html).

Lock містить хеші вибраних Windows/CPython 3.14 коліс, а не універсальний набір для всіх платформ. Для іншої ОС/архітектури/версії Python потрібне окреме свідоме розв’язання й перевірка коліс. Не прибирати hashes для обходу помилки. Не встановлювати backend-залежності в `.venv-api-validation` або глобальний Python. Розв’язання за `.in` призначене для контрольованого оновлення, не повсякденного запуску.

## Runner та мінімальний застосунок

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONUTF8 = '1'
.\.venv-backend\Scripts\python.exe -m pytest tests/infrastructure --collect-only -q
.\.venv-backend\Scripts\python.exe -m pytest tests/infrastructure -q
.\.venv-backend\Scripts\python.exe -m uvicorn car_rental.main:app --app-dir src --host 127.0.0.1 --port 8000 --no-access-log
```

Завершити сервер Ctrl+C. Застосунок не має маршрутів, включно з `/docs`, `/redoc` і `/openapi.json`; відповіді на невідомі URI — лише стандартна поведінка порожнього framework. Це не підтверджує затверджену модель бізнес-помилок. Єдиним погодженим контрактом залишається [api/openapi.yaml](../api/openapi.yaml), він не генерується й не перезаписується під час запуску. CLI Uvicorn перевірено через `--version`; реальний мережевий сервер на цьому етапі не запускався. ASGI-обмін перевірено HTTPX ASGITransport без socket.

Три інфраструктурні перевірки перевіряють імпорти залежностей, HTTPX→ASGI й доступність Europe/Kyiv. Вони не звертаються до БД та не обчислюють календарні правила. pytest знаходить пакет через `pythonpath = ["src"]` у [pyproject.toml](../pyproject.toml); запуск Uvicorn використовує `--app-dir src`. Встановлення локального проєкту через `pip install .` не налаштоване й не потрібне.

Для нового контрольного запуску можна додати `--junitxml=<новий-шлях>.xml`, зберегти stdout/stderr, точну команду, налаштоване середовище й `$LASTEXITCODE` відразу після процесу. Не перезаписувати докази попередніх запусків. Перевірити, що зібрані саме потрібні test ID, exit code відповідає JUnit і журнали не містять чутливих даних; hostname у JUnit прибрати перед передачею. Збір команд/результатів поточного етапу міститься в manifest-файлах звіту. `--no-access-log` у ручному запуску вимикає стандартний запис сирого URI/IP; працює власний безпечний JSON-middleware.

## Журнали

Застосунок пише JSON Lines у stdout: UTC `time`, `event`, `result`, внутрішній `request_id`; `request.start` також має стандартний HTTP `method`, `request.end` — `status` і `duration_ms` за монотонним годинником. Кожний HTTP-запит отримує згенерований id у contextvars, спільний для подій операції та початку/завершення; контекст очищається після запиту. Заголовок/поле request_id до HTTP-контракту не додається. Винятки зберігають ASGI-семантику й не перетворюються логером на нову модель помилок API; журнал не містить їхнього тексту.

`JsonEventLogger.emit(event, result, request_id=..., **fields)` приймає **внутрішні довірені** назви подій/результатів та id, а не дані користувача. Додатково дозволені лише валідний числовий status, скінченна невід’ємна duration_ms і стандартний HTTP method. Інші поля не серіалізуються: body, credentials, контакти, query, URL/IP і сирі винятки не потрапляють у журнал. Не передавати в event/result/request_id вільний текст чи вхідні HTTP-значення. Для запиту id надає middleware; для подій поза запитом потрібен явний внутрішній id.

`record_test_run(path, run_id=..., command=[...], exit_code=..., result=...)` додає JSONL-запис часу, run_id, точного argv та результату до окремого журналу запусків. Передавати тільки перевірені статичні команди без паролів/токенів/персональних шляхів або інших чутливих аргументів: цей журнал зберігає точні аргументи, а не редагує їх. Для зовнішніх автоматизацій до запуску перевіряти безпечність argv; не передавати stdout/stderr чи тіла запитів у command. У цій передачі функція використана для [runs.jsonl](../logs/tdd/T01/logging-green/runs.jsonl).

Це мінімальний sink, не система збору/ротації журналів; stdout слід збирати в ігнорований `logs/runtime/` у майбутньому середовищі. Не вмикати Uvicorn access-log/SQL echo, які обходять allowlist; перевірка майбутнього середовища залишається окремою роботою. Поточні прогони: 9 тестів логування та 3 smoke-перевірки, окремо від календарного T01.

## Майбутня тестова PostgreSQL

[.env.test.example](../.env.test.example) — конфігурація окремої локальної disposable-БД `car_rental_test` та тестової ролі. Це приклад, він автоматично не завантажується. За потреби скопіювати його в ігнорований `.env.test` і явно передати `TEST_DATABASE_URL` майбутнім інтеграційним тестам. Пароль у URL не вносити; локальні засоби автентифікації (наприклад PGPASSFILE) конфігурувати поза Git і журналами.

Наразі немає клієнтського з’єднання, створення БД, міграцій або очищення таблиць. До інтеграційних тестів слід перевірити фактичну окремість тестового сервера/ролі/БД та заборонити робочі адреси. Саме ім’я БД або `.env` не гарантує ізоляцію. Однаковий `DATABASE_URL` для робочих і тестових даних не використовується. SQLite не підключається. Відсутність PostgreSQL не блокує ці smoke-перевірки й майбутні календарні модульні тести.
