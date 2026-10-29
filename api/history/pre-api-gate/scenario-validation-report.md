# Перевірка статичних відповідей mock API

Дата: 29 жовтня 2026 року, Europe/Budapest. Виконано [check_scenarios.py](mock-tools/check_scenarios.py) через `http://127.0.0.1:4010/api/v1`. Джерела запитів і очікувань: [OpenAPI](openapi.yaml), [48 POS](positive-scenarios.md) та погоджені запити-носії [103 NEG](negative-scenarios.md). Це наступний етап після підготовки цих документів, а не виконання негативних бізнес-запитів.

Детальні фактичні запити-носії, статуси, заголовки, JSON/текст тіл, очікувані examples і результат кожного твердження збережено в [scenario-validation-results.json](scenario-validation-results.json), поза ігнорованим runtime. JSON містить час запуску зі зміщенням, команду, версії залежностей, SHA-256 усіх трьох вхідних документів та ADD-001. Поточний SHA-256 OpenAPI: `88989941676702EE28C13D5A16A1320D3636F97B100958CEE48021A59BE8282E`. Останній запуск: 2026-10-29T17:02:06+01:00 — 2026-10-29T17:02:08+01:00.

Погоджені правила спочатку оформлено в [ADD-001](../spec/srs-addendum-001.md): REQ-F-093–REQ-F-096, 11 нових AC та BDD-017–BDD-020. Потім узгоджено API й OpenAPI. Методи, URI, поля схем, HTTP-коди, security та строгість перевірок збережено; додано 10 календарних named examples, POS-042–POS-048 та NEG-095–NEG-103. Перевірочний скрипт тепер вимагає рівно 48 POS і 103 NEG, без пропусків нумерації.

Попередні **135 PASS / 0 FAIL**, їхню специфікацію, сценарії та звіти збережено незмінними у [history/addendum-001-baseline/](history/addendum-001-baseline/). Новий JSON через baseline_evidence містить шлях, хеш і підсумок цього архіву. Первісний запуск **129 PASS / 6 FAIL Location** також збережено окремо в [scenario-validation-results-before-location-fix.json](scenario-validation-results-before-location-fix.json); його історія та виправлення наведені нижче. Історичні результати не приписуються поточній специфікації.

## Команда й середовище

Windows PowerShell, Python 3.14.0; наявні openapi-schema-validator 0.9.0 (OAS31Validator з FORMAT_CHECKER), jsonschema 4.26.0, referencing 0.37.0, PyYAML 6.0.3. Mock: Prism 5.16.0, Caddy 2.11.7, переносний Node.js 24.18.0. Нові залежності не встановлювалися.

Від кореня репозиторію:

```powershell
# Для перезапуску mock з актуальною специфікацією:
powershell -NoProfile -ExecutionPolicy Bypass -File api/mock-tools/stop-mock.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File api/mock-tools/start-mock.ps1

# Валідація OpenAPI та прикладів:
.\.venv-api-validation\Scripts\python.exe -m openapi_spec_validator --schema 3.1 --validation-errors all --subschema-errors all api/openapi.yaml
.\.venv-api-validation\Scripts\python.exe -W default api/validate_openapi.py

# Офлайн-регресія розв’язання Location:
.\.venv-api-validation\Scripts\python.exe -B -m unittest discover -s api/mock-tools -p test_check_scenarios.py -v

# Повна перевірка 151 статичної відповіді:
.\.venv-api-validation\Scripts\python.exe api/mock-tools/check_scenarios.py --base-url http://127.0.0.1:4010/api/v1 --output api/scenario-validation-results.json
```

Mock перезапущено наявними stop/start-скриптами з актуальною специфікацією. Прямий виклик .ps1 спочатку відхилено локальною execution policy; використано наведений запуск PowerShell із Bypass лише для процесу, без зміни системної політики. Усі 151 HTTP-запит виконано після запуску. Mock залишено працювати; зупинка — за [mock-guide.md](mock-guide.md).

Скрипт читає підготовлені команди з Markdown, звіряє OP/маршрут, підключені examples та валідність тіл-носіїв до HTTP-викликів. Перенаправлення не проходить автоматично, щоб не приховати неправильний HTTP-статус. Усі помилки записуються, а наступні сценарії продовжуються. Код завершення: **0** — усі відповіді PASS; **1** — є FAIL; **2** — підготовка/доступність не дозволила розпочати запити, результат NOT_RUN без вигаданих PASS.

## Фактичний результат

**Поточний загальний результат: PASS; код завершення 0.**

| Група | Виконано | PASS | FAIL |
| --- | --- | --- | --- |
| Позитивні статичні відповіді POS-001–POS-048 | 48 | 48 | 0 |
| Статичне відтворення помилок NEG-001–NEG-103 | 103 | 103 | 0 |
| Разом | 151 | 151 | 0 |

Перевірено 1018 застосовних тверджень: **1018 PASS, 0 FAIL**. Ще 6 позначено NOT_APPLICABLE: схема та named example не застосовуються до трьох відповідей 204, але порожність тіла перевірено.

| Що перевірено | Результат |
| --- | --- |
| Очікуваний HTTP-статус | 151/151 PASS |
| Content-Type, розбір JSON, відповідність схемі з форматами, збіг із named example | Усі 148 відповідей з JSON PASS; умовні схеми скасування перевіряє OAS31Validator |
| Порожнє тіло 204 | POS-016, POS-035, POS-041 PASS; Content-Length відсутній або 0 |
| error.code та обов’язкова структура error | Усі 103 статичні помилки PASS; додаткові обмеження details перевірено схемами |
| WWW-Authenticate: Bearer | 10/10 передбачених випадків PASS; для INVALID_CREDENTIALS відсутність Bearer challenge також перевірено |
| Retry-After | 3/3 PASS за схемою й додатністю цілого числа; відлік блокування не перевірявся |
| Allow | NEG-094 PASS; набір GET відповідає URI /bookings/{bookingId} |
| Location | 6/6 PASS: наявність, формат і повна адреса створеного ресурсу після urljoin від фактичного URL запиту |
| Реєстрація без Location | POS-011 PASS |

Обидві команди валідації OpenAPI завершилися з кодом 0: 22 операції, 56 схем, 78 унікальних named examples, усі 482 входження $ref коректні. Залишилися ті самі 4 попередження про невикористані headers/Allow, schemas/CatalogQuery, schemas/AvailabilityQuery, responses/MethodNotAllowed; їх не вимкнено. Окремо пройшли 2 регресійні тести з 13 варіантами Location, без HTTP-запитів.

## Початкові шість розбіжностей та їх виправлення

До виправлення в кожному випадку статус **201**, тіло та named example були правильні, але фактично поверталося **`Location: ../dictionary`**. Початковий SHA-256 OpenAPI: `F0257BA54A93A0E82CB5B0D99CA8AFEF7112DD9DD74BDC9E15B41C9E103FE09D`. Після виправлення фактичні Location збігаються з наведеними очікуваними адресами у всіх шести випадках:

| POS-ID | OP-ID | Очікувана адреса Location |
| --- | --- | --- |
| POS-018 | OP-10 | /api/v1/bookings/booking-example |
| POS-027 | OP-13 | /api/v1/bookings/booking-example/cancellation |
| POS-028 | OP-13 | /api/v1/bookings/booking-example/cancellation |
| POS-029 | OP-13 | /api/v1/bookings/booking-example/cancellation |
| POS-031 | OP-15 | /api/v1/cars/car-example |
| POS-039 | OP-20 | /api/v1/cars/car-example/service-unavailabilities/period-example |

Причина генерації: спільний заголовок мав лише string/uri-reference, без конкретного прикладу адреси. Тепер у responses BookingCreated, CancellationCreated, CarCreated і ServicePeriodCreated задано конкретні Header Objects із прикладами наведених URI. Для трьох варіантів скасування використовується спільний приклад CancellationCreated. Тип string/uri-reference та required=true збережено; загальне визначення Location, яке більше не використовується, прибрано. Приклади описують наявні mock-фікстури, не вводять сталої адреси для всіх майбутніх ресурсів API.

Окремо виправлено перевірку: `urljoin(фактичний_URL_запиту, Location)` спочатку розв’язує абсолютне, кореневе або відносне посилання. Потім порівнюється повна адреса очікуваного створеного ресурсу: схема, host/port, шлях, відсутність зайвих query/fragment та userinfo. Порт за замовчуванням нормалізується. Наприклад, `bookings/booking-example` від POST `/api/v1/bookings` є коректним, хоча його сирий uri.path не дорівнює `/api/v1/bookings/booking-example`. Для скасування коректне відносне `cancellation`. Розв’язаний URL записується в кожну деталь перевірки Location у JSON.

Регресійні тести приймають ці коректні відносні URI, але відхиляють `../dictionary`, інший ресурс, інший origin, подвоєний префікс і зайві query/fragment. Початкові шість FAIL були реальними розбіжностями: `../dictionary` вказує не на створений ресурс також після правильного urljoin. Перевірки не вимикалися й не послаблювалися.

## Межі висновку та зміни документації

NEG виконано **лише як вибір статичних помилок через валідні носії та Prefer**. Успіх цих 103 перевірок не доводить, що відсутній Bearer, заборонена роль, чуже бронювання, неправильний період чи інша негативна умова справді відхиляються системою. Generic VALIDATION_ERROR повертає погоджений статичний field="$", а не діагностику конкретного невалідного поля. У NEG-094 виконувався дозволений GET із вибором 405, а не реальний PATCH.

Не перевірено бізнес-логіку, справжню автентифікацію, ролі/власність, DST/календарні розрахунки, конкурентність, актуальність ціни, відлік блокування, збереження даних або автоматичні переходи станів. Строк сесій, наслідки зміни пароля та Q-07 закриті ADD-001. **Mock не перевіряє реальне завершення сесій, анулювання токенів або календарні обчислення**: 401 та календарні Quote обрано через Prefer, не отримано виконанням нових правил. Backend і БД не створено. **API-GATE не виконано й не оголошено пройденим.**

У передумовах NEG-020 залишено лише власний профіль, у NEG-021 — автомобіль; зайву згадку службового періоду прибрано. NEG-022 про службовий період збережено. Коміту та push немає.

Глобальну spec/traceability-matrix.md для пункту 16 не оновлено. Backend, коміт і push не виконано.
