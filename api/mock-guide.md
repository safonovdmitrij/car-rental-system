# Локальний mock REST API

Підготовлено й перевірено 29 жовтня 2026 року. Джерело операцій, схем і прикладів — незмінений [openapi.yaml](openapi.yaml), OpenAPI **3.1.0**. SHA-256: `0A7C912B06EE51067C5BBD56A16EA90379F2CCE1352ED94DAE16BBA37B1A2F99`.

## Інструменти й адреса

| Компонент | Версія | Призначення |
| --- | --- | --- |
| Stoplight Prism CLI | 5.16.0 | Готовий mock із маршрутів і named examples OpenAPI; статичний режим |
| Node.js / npm | 24.18.0 / 11.16.0 | Переносне Windows x64 середовище для Prism; без глобального встановлення |
| Caddy | 2.11.7 | Готовий reverse proxy, який зберігає зовнішній префікс /api/v1 |
| openapi-schema-validator | 0.9.0, OAS31Validator | Незалежна перевірка фактичних HTTP-тіл за оригінальними схемами з перевіркою форматів |

Адреса для клієнта: **http://127.0.0.1:4010/api/v1**. Внутрішня адреса Prism — `http://127.0.0.1:4011`; обидва процеси слухають лише loopback. Це локальний HTTP mock; вимогу HTTPS продуктивного середовища не змінено.

Prism [приймає OpenAPI 3.1](https://github.com/stoplightio/prism), але [не додає шлях із servers.url до своїх маршрутів](https://github.com/stoplightio/prism#-faqs). Тому [Caddyfile](mock-tools/Caddyfile) монтує Prism під `/api/v1` через `handle_path`: зовні `/api/v1/cars`, всередині `/cars`. Це лише маршрутизація готовим proxy, без обробників операцій, бізнес-логіки чи БД. OpenAPI не перетворюється й не знижується до 3.0; префікс у контрактних URI застосовується рівно один раз.

## Встановлення у Windows PowerShell

Усі команди виконуються від кореня репозиторію. Потрібні Windows x64, PowerShell 5.1+ та доступ до офіційних джерел завантаження.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File api/mock-tools/install-mock.ps1
```

[install-mock.ps1](mock-tools/install-mock.ps1) завантажує переносні Node.js і Caddy у `.mock-runtime/`, перевіряє архів Node за офіційним SHA-256, Caddy — за офіційним SHA-512, і виконує `npm ci` за [package-lock.json](mock-tools/package-lock.json). Прямий пакет зафіксовано як `@stoplight/prism-cli: 5.16.0` у [package.json](mock-tools/package.json); залежності також зафіксовано lock-файлом. Сторонні install-скрипти не запускаються (`--ignore-scripts`); глобальний Node/npm і системний PATH не змінюються. Bypass застосовано лише до процесу запуску скрипта, не як постійну системну політику.

Еквівалентна команда npm після завантаження переносного Node:

```powershell
$mockNodeDirectory = (Resolve-Path '.mock-runtime/node-v24.18.0-win-x64').Path
$env:Path = $mockNodeDirectory + ';' + $env:Path
& "$mockNodeDirectory/npm.cmd" ci --prefix api/mock-tools --ignore-scripts --no-audit --no-fund --cache .mock-runtime/npm-cache
```

Для незалежної перевірки тіл використовується середовище з попереднього [етапу валідації](validation-report.md). Якщо його ще немає:

```powershell
python -m venv .venv-api-validation
.\.venv-api-validation\Scripts\python.exe -m pip install --disable-pip-version-check -r api/validation-requirements.txt
```

## Запуск і зупинка

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File api/mock-tools/start-mock.ps1
```

[start-mock.ps1](mock-tools/start-mock.ps1) перевіряє, що 4010/4011 вільні, запускає Prism і Caddy у прихованих фонових процесах, очікує готовності та друкує адресу й PID. Prism отримує безпосередньо `api/openapi.yaml`, без `--dynamic` чи `--ignoreExamples`. Caddy запускається після відкриття порту Prism, щоб уникнути стартових 502. Схеми з OpenAPI не переписуються.

Логи й стан процесів: `api/mock-tools/runtime/`. Цей каталог, `node_modules/` і переносні бінарні файли виключені через `.gitignore`. Caddy зберігає допоміжні дані всередині `.mock-runtime/`, не в профілі Windows: storage налаштовано через Caddyfile, XDG_DATA_HOME/XDG_CONFIG_HOME — лише для дочірнього процесу, за [правилами Caddy](https://caddyserver.com/docs/conventions#data-directory). Його admin API та автоматичний TLS вимкнені для локального mock.

Зупинка:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File api/mock-tools/stop-mock.ps1
```

[stop-mock.ps1](mock-tools/stop-mock.ps1) зупиняє лише збережені PID після звірки шляху executable і часу створення процесу, щоб не завершити інший процес після повторного використання PID. Запуск → HTTP-перевірки → зупинка перевірені фактично; після цього mock повторно запущено й залишено працювати.

Для ручного запуску в двох окремих терміналах, зупинка — Ctrl+C у кожному:

```powershell
# Термінал 1, корінь репозиторію
& '.mock-runtime/node-v24.18.0-win-x64/node.exe' 'api/mock-tools/node_modules/@stoplight/prism-cli/dist/index.js' mock api/openapi.yaml --host 127.0.0.1 --port 4011
```

```powershell
# Термінал 2, той самий корінь
$env:XDG_DATA_HOME = Join-Path (Get-Location).Path '.mock-runtime/caddy-app-data'
$env:XDG_CONFIG_HOME = Join-Path (Get-Location).Path '.mock-runtime/caddy-app-config'
& '.mock-runtime/caddy-2.11.7/caddy.exe' run --config api/mock-tools/Caddyfile --adapter caddyfile
```

Не запускай одночасно фоновий і ручний варіанти на тих самих портах. Для ручного варіанта stop-mock.ps1 не підміняє Ctrl+C: він працює з процесами, зареєстрованими start-mock.ps1.

## Два перевірені HTTP-запити

```powershell
$mockBase = 'http://127.0.0.1:4010/api/v1'
$catalogResponse = Invoke-WebRequest -UseBasicParsing -Method Get -Uri "$mockBase/cars" -Headers @{
    Accept = 'application/json'
    Prefer = 'code=200, example=PublicCarList'
}
$catalogResponse.StatusCode
$catalogResponse.Content
```

```powershell
$quoteBody = @{
    carId = 'car-example'
    startsAt = '2026-11-12T09'
    endsAt = '2026-11-14T09'
} | ConvertTo-Json -Compress
$quoteResponse = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$mockBase/booking-quotes" -ContentType 'application/json' -Headers @{
    Accept = 'application/json'
    Authorization = 'Bearer mock-client'
    Prefer = 'code=200, example=Quote'
} -Body $quoteBody
$quoteResponse.StatusCode
$quoteResponse.Content
```

`mock-client` — довільний демонстраційний рядок, не справжня сесія. Значення запиту взяті з поточного QuoteRequest example. Приклади не «старіють» як mock-дані: mock не виконує перевірки поточного часу чи горизонту оренди.

Автоматичний повтор саме цих двох запитів і перевірки префікса:

```powershell
.\.venv-api-validation\Scripts\python.exe api/mock-tools/check_mock.py
```

[check_mock.py](mock-tools/check_mock.py) читає request example, response schemas та expected named examples із поточного OpenAPI. Надсилає справжні локальні HTTP-запити, перевіряє статус, Content-Type, відповідність тіла схемі через OAS31Validator та точний збіг із вибраним прикладом. Не містить обробників API чи календарних/цінових обчислень. Фактичні тіла зберігає в `api/mock-tools/runtime/smoke-results.json` разом із хешем специфікації.

| Перевірка | Фактичний результат |
| --- | --- |
| GET /api/v1/cars | 200, application/json; схема й PublicCarList MATCH. Один car-example, characteristics: Марка=Porsche, Модель=911, dailyRate="1500.00", currency=UAH |
| POST /api/v1/booking-quotes | 200, application/json; схема запиту й відповіді PASS, Quote MATCH. car-example; billableDays=2; totalPrice="3000.00"; priceConfirmationToken="price-confirmation-example" |
| GET /cars на зовнішньому порту 4010 | 404 від proxy: немає погодженого префікса |
| GET /api/v1/api/v1/cars | 404 від маршрутизації Prism: префікс подвоєно |

Останні дві перевірки стосуються лише адресації, а не відповідності 404 бізнес-моделі помилок. Специфікація зберегла початковий SHA-256; усі 22 операції завантажено Prism, але HTTP-перевірки успішних відповідей виконано лише для OP-01 та OP-09.

## Вибір прикладів для наступних сценаріїв

Prism дозволяє [вибирати статус і named example заголовком Prefer](https://github.com/stoplightio/prism/blob/v5.16.0/docs/guides/01-mocking.md). Назва має бути ключем у `content.application/json.examples` саме вибраної відповіді операції; приклади беруться через $ref із components/examples.

| Майбутній вибір | Операція | Заголовок Prefer |
| --- | --- | --- |
| Публічний каталог | GET /cars | code=200, example=PublicCarList |
| Адміністративне представлення каталогу | GET /cars | code=200, example=AdminCarList |
| Попередній розрахунок | POST /booking-quotes | code=200, example=Quote |
| Недоступне авто | POST /booking-quotes або POST /bookings | code=409, example=CAR_UNAVAILABLE |
| Зміна ціни | POST /bookings | code=409, example=PRICE_CHANGED |
| Помилка валідації | Операція, що має відповідь 422 | code=422, example=VALIDATION_ERROR |

Для наступних сценаріїв передавай валідний для операції запит і демонстраційний Bearer, якщо він потрібний, а статус/приклад вибирай через Prefer. Навмисно пошкоджений запит може запустити власну діагностику Prism й змінити вибрану відповідь. Вибір AdminCarList є ручним вибором проєкції, а не перевіркою ролі. Помилкові відповіді з цієї таблиці лише підготовлено для наступного етапу: у поточному кроці їх не запитували; сценарії пунктів 11–12 не виконувалися.

## Обмеження та попередження

- Сумісність у цьому кроці підтверджена для завантаження документа 3.1.0, named examples і двох перевірених тіл. Це не вичерпна перевірка всіх можливих комбінацій JSON Schema 2020-12. Prism виконує власну нормалізацію схем; строгий висновок про відповідність тіл робить незалежний OAS31Validator за незміненим контрактом. Динамічну генерацію не використовуємо.
- Власні помилки маршрутизації/валідації Prism можуть мати application/problem+json та технічну діагностику, відмінні від ErrorResponse; proxy також може повернути транспортний 502, якщо Prism зупинено. Це обмеження інструментів, не зміна API-контракту. Для перегляду погоджених бізнес-помилок слід явно вибирати їхні named examples.
- Bearer перевіряється інструментом лише як форма/наявність заголовка. Немає реальних облікових записів, ролей, перевірки власності, строку сесії чи збереження даних. Статичний Quote не доводить розрахунку ціни, доступності, календарних правил або актуальності тарифу; зміна тіла не змушує mock перерахувати приклад.
- Встановлення npm видало попередження deprecation для транзитивних json-schema-ref-parser@6.1.0, uuid@8.3.2 та @faker-js/faker@5.5.3. Їх не приховано; транзитивні версії не замінювалися довільно всупереч lock-файлу. npm 11.16.0 також повідомив про доступну новішу major-версію; автоматичного оновлення не виконували.
- Caddy повідомляє `admin endpoint disabled` — очікувана конфігурація локального proxy. Збереження даних Caddy перенесено в каталог проєкту; HTTP/1 задано явно для локального HTTP. Це не додаткові властивості REST API.

API-GATE не виконано й не оголошено пройденим. Строк сесій, вплив зміни пароля на сесії та Q-07 залишаються невирішеними. Серверну реалізацію й БД не створено; коміту та push немає.
