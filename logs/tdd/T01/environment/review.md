# T01: середовище та мінімальний runner

Дата: 30.10.2026. Виконавець: Codex. Обсяг дозволено повідомленням користувача після коміту `d4d3703` та [preparation-decisions.md](../preparation-decisions.md), крок 2. Початковий Git status порожній, гілка main. AGENTS.md пошуком не знайдено; чинна конвенція комітів перечитана. Сторонні зміни відсутні; add/commit/push не виконувалися.

## Результат

Створено окремий `.venv-backend`, мінімальний `src/car_rental` без бізнес-маршрутів, конфігурацію pytest, три інфраструктурні тести, приклад майбутньої окремої PostgreSQL, [інструкцію запуску](../../../../docs/backend-setup.md). Немає календарного коду/тестів, міграцій, створення чи підключення БД, JSON-middleware. Наявне `.venv-api-validation` не змінювалося; OpenAPI не редагувався. Це не TEST-GATE/G-READY або Validation і не календарний RED/GREEN.

`uv` у PATH відсутній. Використано CPython 3.14.0 / Windows x86-64 та pip 25.2 із нового venv, без глобальної установки. Вибір версій делеговано користувачем; сумісність перевірена розв’язувачем, імпортами та smoke-прогоном. Точні прямі й транзитивні версії/хеші — [backend.lock](../../../../requirements/backend.lock).

| Залежність | Встановлена версія |
| --- | --- |
| FastAPI | 0.162.0 |
| Uvicorn | 0.54.0 |
| SQLAlchemy | 2.1.6 |
| psycopg / psycopg-binary | 3.3.6 / 3.3.6 |
| Alembic | 1.20.1 |
| pytest | 9.2.0 |
| HTTPX | 0.28.1 |
| Pydantic / Starlette | 2.14.2 / 1.10.0 |
| tzdata | 2026.6 |

Фіксація відтворює вибрані колеса на цій платформі, не заявляє універсальну переносність. 30 дистрибутивів, включно з opentelemetry-api як транзитивною залежністю FastAPI; сервіс телеметрії, експортер або його конфігурація не створювалися.

## Команди та докази

Перед підбором: `python -m venv .venv-backend` — exit 0; pip нового середовища 25.2. Розв’язання:

`.\.venv-backend\Scripts\python.exe -m pip --isolated install --dry-run --ignore-installed --only-binary=:all: --index-url https://pypi.org/simple --report .backend-setup/resolution.json -r requirements/backend.in --quiet`

Початкова спроба без --quiet — exit 1 через sandbox WinError 10013, мережа недоступна; це не конфлікт версій і не RED. Дозволений запуск із мережевим доступом також завершився exit 1: агент не створив батьківський каталог звіту `.backend-setup`. Каталог створено, та сама операція повторена — exit 0. Із metadata/version та archive_info/hashes/sha256 звіту pip сформовано відсортований lock з точними `==` та hashes всіх 30 коліс.

Установка лише в нове середовище:

`.\.venv-backend\Scripts\python.exe -m pip --isolated install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r requirements/backend.lock --disable-pip-version-check`

Exit 0; установлені всі 30 дистрибутивів. Сирі службові metadata й installation-output залишені в ігнорованому `.backend-setup`, не включаються до коміту; набір фактичних версій відображено в lock і цьому звіті. Початкові збої підготовки не приховані й не зараховуються за падіння тестів.

| Контроль | Результат і аналіз |
| --- | --- |
| `python -m pip check` | Exit 0: No broken requirements found; [output](pip-check.txt) |
| Окремий import усіх основних пакетів | Exit 0: Dependency imports: PASS; [output](imports.txt) |
| Початковий collect/smoke | Exit 0; 3 зібрано / 3 PASS, але 1 deprecation warning про HTTPX у Starlette TestClient; [manifest](manifest.json), [collect](collect.txt), [smoke](smoke.txt), [JUnit](smoke.xml). Це не бізнес-RED і не помилка залежностей |
| Виправлення smoke-транспорту | Замість TestClient використано HTTPX AsyncClient/ASGITransport та asyncio.run; нових залежностей/бізнес-поведінки не додано. Через зміну тесту повторено collection і smoke окремим запуском |
| Фінальний collect/smoke | Exit 0; рівно 3 зібрано, 3 PASS, 0 FAIL/ERROR/SKIP, без попереджень; [manifest](manifest-final.json), [collect](collect-final.txt), [smoke](smoke-final.txt), [JUnit](smoke-final.xml). Усі три потрібні test ID присутні; exit code відповідає JUnit |
| Uvicorn CLI | `python -m uvicorn --version` — exit 0, 0.54.0 / CPython 3.14.0 / Windows; live TCP-сервер не запускався |

У командах таблиці `python` означає виключно `.venv-backend/Scripts/python.exe`; точні команди, UTC-час і exit code прогонів — у manifest-файлах. Фінальний manifest містить hashes кінцевих тесту, bootstrap, lock та OpenAPI. Перший manifest містить hash початкового тесту до заміни deprecated TestClient; він історичний і не приписується кінцевому файлу. Машинний hostname у двох JUnit замінено на `local` перед передачею; результати/test ID/час збережені.

Після кожного контрольного запуску прочитано stdout/stderr; початкові журнали мали тільки зазначене warning, фінальні — без warnings або падінь. Дані синтетичні; запит не містив тіла/токена/контактів. Перевіряються відсутність секретів/PII в артефактах, source hashes, збіг установлених дистрибутивів з lock, існування Markdown-посилань, чистий Git index та whitespace перед передачею.

Підсумкова перевірка виконана: [verification.json](verification.json) — 30/30 установлених версій збігаються з lock, venv ізольований без system-site-packages, кінцеві source hashes та затверджений хеш OpenAPI збігаються, JUnit підтверджує 3 PASS без FAIL/ERROR/SKIP, 20 локальних посилань на момент перевірки існують, скан журналів без чутливих значень, Git index порожній, git diff --check — exit 0. [actions.jsonl](actions.jsonl) фіксує команди підготовки, результати й виправлені інфраструктурні збої; recorded_at — час складання журналу, а точний час тестових запусків збережено в manifest. Окремий TCP-прогін і відтворення на іншій платформі не виконувалися.

## Що лишається наступним етапам

Три smoke-тести підтверджують лише інфраструктуру: імпорти, ASGI transport та доступність даних Europe/Kyiv. PostgreSQL/міграції/реальний HTTP контракт, календарні правила, JSON-логування/request_id та fault handling не перевірені. Конфігурація PostgreSQL підготовлена без вибору/запуску сервера; реальну ізоляцію ще слід забезпечити перед інтеграцією. Календарних тестів — 0, бізнес-RED — немає. Необхідність належних G-SPEC/G-PLAN/G-READY не змінена цим технічним результатом.

Наступна межа — **тести логування та фактичний RED**, з окремою зупинкою до реалізації логування. Календарна реалізація не дозволена. Вибір засобу та сумісних версій виконано в межах делегованого рішення; додаткового погодження стеку для цього setup не потрібно.
