# Мінімальне логування: GREEN

Дата: 30.10.2026. Виконавець: Codex. Підстава: пряме доручення користувача реалізувати логування після перевірки окремого RED-коміту. Перед змінами: main, чистий Git status, HEAD `2ea840f4f5fbda178dff19e0793946cea6aa98c0` (`test: specify logging behavior and capture infrastructure RED`). Цей коміт містить test_logging.py, observability.py із заглушками й усі файли [доказів RED](../logging-red/review.md). Порівняння з HEAD до реалізації не виявило незакомічених змін. AGENTS.md пошуком не знайдено; рішення підготовки, план §8, setup, конвенція комітів та RED-тести/докази прочитані.

## Огляд очікувань і реалізація

Дев’ять наявних тестів перевіряють внутрішню схему JSON, allowlist при success/error, HTTP start/end/status/duration, спільний request_id для переплетених запитів, відсутність чутливих значень при помилці та окремий журнал запусків. Хибних очікувань у цьому обсязі не виявлено, **тести не змінювалися**. Це інфраструктурний TDD, не календарні або бізнес-контрактні тести.

[observability.py](../../../../src/car_rental/observability.py) реалізує:

- JsonEventLogger: по одному JSON-об’єкту на рядок, UTC-час, event/result/request_id; додаткові поля лише status, duration_ms, method з перевіркою типів/значень. Непередбачені поля ігноруються без перетворення на рядок, зокрема тіло, credentials, контакти й сирі винятки.
- RequestLoggingMiddleware: власний випадковий id для кожного HTTP-запиту, ContextVar з відновленням попереднього контексту у finally, request.start та request.end, фактичний статус із ASGI response.start, тривалість perf_counter. За винятку до response.start — status 500/result error, без тексту винятку. Виняток повторно піднімається зі збереженням ASGI-семантики; non-HTTP scope делегується застосунку.
- current_request_id: доступ до активного внутрішнього контексту; поза запитом без явного id дає безпечну помилку, а не використовує чужий id.
- record_test_run: append у окремий UTF-8 JSONL, UTC time/run_id/точний command argv/exit_code/result. Функція фактично використана для [runs.jsonl](runs.jsonl) цієї передачі, не лише тестується на tmp_path.

[main.py](../../../../src/car_rental/main.py) підключає middleware із JSON sink у stdout; маршрутів чи нових HTTP-полів немає. Інструкція [backend-setup.md](../../../../docs/backend-setup.md) оновлена щодо stdout, внутрішніх event-labels, безпечних статичних команд і вимкненого стандартного access-log.

Основні labels/id та command є довіреними технічними значеннями від коду/оркестратора: API не приймає їх від користувача. Журнал запусків навмисно зберігає точний argv, тому передавати в command секретні аргументи або персональні шляхи заборонено; поточні команди перевірені й таких аргументів не мають. Ні middleware, ні logger не читають/журналюють request headers, body, query, client IP або raw URL. Request_id у відповідь чи обов’язковий заголовок не додається.

## Фактичні прогони та аналіз

Точні команди, середовище, версії, UTC-час початку/завершення й hashes — у [manifest.json](manifest.json). Python 3.14.0, pytest 9.2.0, FastAPI 0.162.0, HTTPX 0.28.1; lock та залежності не змінено. PYTHONUTF8=1, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, PYTHONPATH=src; cacheprovider вимкнений, basetemp локальний та ігнорований.

| Запуск | Результат / аналіз |
| --- | --- |
| test_logging.py | Exit 0, **9 PASS**; [stdout](logging.txt), [JUnit](logging.xml). Усі дев’ять випадків RED тепер виконують assertions до кінця, включно з privacy та concurrent correlation; немає FAIL/ERROR/SKIP і попереджень |
| test_environment.py | Exit 0, **3 PASS**; [stdout](smoke.txt), [JUnit](smoke.xml). Імпорти, підключений ASGI bootstrap і tzdata працюють; регресії smoke-набору немає |
| Окрема error-проба | Exit 0; [probe.py](probe.py), [stdout](probe.txt), [безпечні події](error-events.jsonl). HTTP 500; request.start, operation.complete, request.end мають один id; остання подія status=500/result=error; контекст після запиту очищений |

Невдалих спроб до GREEN у цьому етапі **не було**: обидва набори пройшли з першого запуску після реалізації; окрема проба теж пройшла відразу. Історичні падіння залишено в RED-коміті, вони не переписані й не видалені. Жодних проміжних файлів-дублікатів у робочому дереві не створювалося; тимчасові pytest-файли залишаються ігнорованими. Досягнення GREEN не обґрунтовувалося зміною тестів/виключенням випадків.

Повторний цільовий запуск (для нових доказів використовувати нові шляхи):

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONPATH = 'src'
.\.venv-backend\Scripts\python.exe -m pytest tests/infrastructure/test_logging.py tests/infrastructure/test_environment.py -q --tb=short --assert=plain --show-capture=no -p no:cacheprovider --basetemp=.backend-setup/logging-next-temp
```

Це зручна об’єднана команда для майбутнього повтору. Фактично в цій передачі два файли запускалися окремими командами з окремими JUnit; точні argv збережено у manifest і runs.jsonl.

## Перевірка безпечності та межі

У тестах є лише синтетичні canary-значення. Тести перевіряють allowlist та відсутність значень у записаному JSON, зокрема коли ASGI-app кидає виняток із тілом запиту. Окрема проба додатково передала canary-тіло з password/email/phone/name, Bearer credential і query; app спробував записати тіло як exception-поле й кинув RuntimeError із цим тілом. Logger не серіалізував небезпечні поля, middleware записав error без винятку. Лише після перевірки canary та allowlist збережено error-events.jsonl. Події реально існують, тому приватність не доводиться порожнім журналом.

Після кожного прогону прочитано stdout/stderr, зіставлено exit code з результатами; JUnit hostname замінено на local. Фінальна перевірка звіряє 12 test ID/результатів, hashes, canary/email/персональні шляхи в доказах, локальні Markdown-посилання, незмінність тестів/RED-історії/контракту, git diff --check та status. [verification.json](verification.json) містить фактичний підсумок; [actions.jsonl](actions.jsonl) — дії агента. Сам probe.py містить тільки штучні маркери, а не реальні секрети; вони не є runtime-журналом.

Цей результат підтверджує власний JSON sink та мінімальний ASGI-шар, а не всі можливі сторонні log handlers. Збір/ротація, обробка streaming/disconnect, production-конфігурація серверного error-log, зовнішні експортери та подальші бізнес-події ще не приймалися. Повторно піднятий виняток може обробляти зовнішній сервер; його конфігурація не повинна виводити чутливі exception values. API-модель аварійних відповідей не реалізовувалася цим етапом.

SHA-256 затвердженого OpenAPI залишається `88989941676702ee28c13d5a16a1320d3636f97b100958cee48021a59be8282e`. Календарні правила та тести T01/F007 не створювалися. **TEST-GATE, G-READY і Validation не оголошуються пройденими.** Git add/commit/push не виконувалися. Зупинка після GREEN для перегляду й коміту користувачем.

Пропонована назва коміту: `feat: implement structured logging and capture infrastructure GREEN`.
