# Запуск базового REST API

Реалізовано 22 операції затвердженого [OpenAPI](../api/openapi.yaml). [Підсумок та незавершене](../logs/tdd/base-implementation-review.md), [рішення користувача](../logs/tdd/implementation-decisions.md). Фінальна регресія — 231 PASS; це не приймання всіх NF-вимог чи людський G-READY.

## Середовище

Windows x86-64, CPython 3.14.0, pip 25.2. uv недоступний, використано venv/pip. `.python-version` документує версію, але не встановлює Python. Команди виконуються з кореня репозиторію; активація venv не потрібна.

```powershell
python --version
# Лише для нового середовища:
python -m venv .venv-backend
.\.venv-backend\Scripts\python.exe -m pip --isolated install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r requirements/backend.lock
.\.venv-backend\Scripts\python.exe -m pip check
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
```

[backend.in](../requirements/backend.in) — прямі залежності; встановлювати [backend.lock](../requirements/backend.lock): 45 дистрибутивів із точними версіями та SHA-256 Windows/Python 3.14 коліс. Для іншої платформи потрібні окреме розв’язання й перевірка, не видалення hashes. `.venv-api-validation` та mock-середовище не змінювати. Argon2id m=19 MiB/t=2/p=1 погоджено користувачем; OpenAPI-валідатор додано для реального API за незмінним YAML.

## Окремий тестовий PostgreSQL

Створено кластер **лише в `.backend-setup/postgres-test`**, loopback:55432, роль car_rental_test. Робочий PostgreSQL-сервіс не використовувався. Після фінальних тестів власний тестовий процес зупинено, файли збережено; перевірити або запустити його можна встановленими бінарними файлами:

```powershell
$testPgBin = 'D:\IDE\postgres\bin'
& "$testPgBin\pg_ctl.exe" -D .backend-setup/postgres-test status
# Якщо він зупинений:
& "$testPgBin\pg_ctl.exe" -D .backend-setup/postgres-test -l .backend-setup/postgres-test.log -o '-h 127.0.0.1 -p 55432' -w start
```

Для чистого checkout спочатку створити цей каталог через initdb із новим окремим data_directory; не ініціалізувати наявні дані. Локальний disposable-кластер використовує trust тільки для синтетичних даних; це не production-конфігурація. [.env.test.example](../.env.test.example) задає TEST_DATABASE_URL; `.env.test` автоматично не завантажується. Фікстури перевіряють SHOW data_directory, відмовляються писати поза зазначеним кластером і створюють UUID-схеми через Alembic. SQLite не використовується.

## Міграції й застосунок

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://car_rental_test@127.0.0.1:55432/postgres'
.\.venv-backend\Scripts\python.exe -m alembic upgrade head
.\.venv-backend\Scripts\python.exe -m uvicorn car_rental.main:app --app-dir src --host 127.0.0.1 --port 8000 --no-access-log
```

Завершити сервер Ctrl+C. Міграції запускаються явно; [0001_base](../migrations/versions/0001_base.py) незалежна від майбутніх Python-моделей. Для робочого середовища DATABASE_URL задається окремо й свідомо; секрети не передавати через Git/argv/журнали. Адміністратор провізіонується довіреним адміністратором БД поза публічним API; реєстрація завжди створює лише client. Ізольований тестовий приклад — fixture admin у [conftest.py](../tests/integration/conftest.py).

`/docs`, `/redoc` і `/openapi.json` відключені. Погоджений YAML не генерується/перезаписується; API читає його для валідації запитів. Тести перевіряють відповіді за ним, а не за схемою, виведеною з коду.

## Перевірки й докази

```powershell
# Без PostgreSQL:
.\.venv-backend\Scripts\python.exe -m pytest tests/infrastructure tests/unit -q -p no:cacheprovider
# Повний набір потребує зазначеного кластера:
$env:TDD_CONTRACT_CHECK = '1'
.\.venv-backend\Scripts\python.exe -m pytest tests -q --tb=line --assert=plain --show-capture=no -p no:cacheprovider --basetemp=.backend-setup/manual-tests
```

test_https.py використовує наявний `.mock-runtime/caddy-2.11.7/caddy.exe`, перевіряє справжній TLS через явний CA-файл, не встановлює глобальну довіру та завершує свої процеси. Ключі лишаються в ігнорованому basetemp. Production/browser trust не прийнято. [transport.py](../src/car_rental/transport.py) генерує локальний loopback-only proxy config; довготривале розгортання потребує окремого сертифіката й керованого запуску.

`scripts/tdd_run.py <package> <new-phase> <test-paths> [--expect 1]` зберігає точну команду, exit code, test IDs, stdout, очищений JUnit і runs.jsonl. Існуючу фазу не перезаписує; для успішної регресії `--expect 1` не використовувати. Помилки середовища не є бізнес-RED. Реальні команди — у manifest.json пакетів.

З TDD_CONTRACT_CHECK відповіді перевіряються в пам’яті. Профілі/токени не експортуються; contract-checks.jsonl містить метод, синтетичний шлях, статус і результат. api-events.jsonl містить фактичні безпечні події; після прогону перевіряти пари start/end за request_id, очікувані коди й відсутність чутливих значень. [Фінальний аналіз](../logs/tdd/F01/FINAL/contract-and-log-review.json).

## Логування й копії

JSON Lines у stdout: UTC time, event, result, request_id, дозволені method/status/duration_ms; значущі дії пишуться після commit. Немає тіл/заголовків/query/IP/контактів/паролів/токенів/сирих винятків. ContextVar розділяє запити; обов’язковий HTTP-заголовок чи поле request_id не додається. Labels та явний id — довірені технічні значення, не вхідні HTTP-дані. Сторонні access-log/SQL echo й production error-log потребують безпечної конфігурації.

record_test_run зберігає точний перевірений argv, run_id, час, exit_code/result; не передавати туди секретні аргументи, контакти чи персональні шляхи. Ротація/централізований збирач лишаються deployment-роботою.

Для добового резервування підготовлено окремий single-worker `python -m car_rental.backups`. PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSFILE задають підключення, PG_DUMP — шлях до pg_dump, BACKUP_DIR — ігнорований каталог копій. Раз на хвилину worker перевіряє успішну копію поточної UTC-дати; checkpoint переживає restart, збій дозволяє повтор. `--once` — діагностика. Windows task/service агент не реєстрував. Сирі dumps не комітити.

Є unit-доказ scheduler та реальний pg_dump/list diagnostic. Q-08, аварійне відновлення/RPO/RTO, production-приймання N01, Q-10/браузерна продуктивність і UI-сумісність відкриті за [підсумком](../logs/tdd/base-implementation-review.md). Увесь API готовим не оголошено.
