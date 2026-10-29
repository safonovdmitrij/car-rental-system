# Негативні сценарії REST API

**Статус: підготовлено, не виконано.** Джерела: [OpenAPI](openapi.yaml), [модель помилок](error-model.md), [вимоги API](requirements.md), [трасованість](traceability.md), [схеми](data-schemas.md). Структура карток і клієнтський спосіб виклику узгоджені з [позитивними сценаріями](positive-scenarios.md); запуск mock описано в [інструкції](mock-guide.md).

## Межа майбутнього тесту системи й статичного mock

Кожен NEG — окрема ізольована фікстура. За замовчуванням контрольований час системи — 2026-11-10T12:00:00+02:00; інший час указано явно. Ресурси, записи, лічильники входу й токени готуються до сценарію, не отримуються попередніми NEG/POS. Якщо сценарій не перевіряє роль/власність, роль дозволена й власність дотримана. Не визначаємо нового пріоритету незалежних помилок.

**Негативний запит у картці** призначений для майбутньої реалізації системи: саме він має порушувати зазначене правило. **Mock-команда** навмисно використовує валідний запит-носій до відомої операції, демонстраційний Bearer, якщо потрібний, і Prefer: code=…, example=…. Вона лише вибирає наявний ErrorResponse з OpenAPI. Це не той самий запит і не доказ, що Prism перевірив порушення. Навмисно невалідні тіло, метод, URL або відсутній Bearer можуть натомість дати власний application/problem+json Prism, тому вони не використовуються для детермінованого показу погодженої помилки.

Для всіх запланованих перевірок системи: статус і code мають збігатися з карткою; Content-Type — application/json. Усі три поля error.code, error.message та error.details обов’язкові: code — погоджений машинний код, message — українською, details — об’єкт. Для VALIDATION_ERROR потрібен непорожній details.fields з об’єктами {field, message}; для PRICE_CHANGED — details.quote за схемою Quote; для решти кодів — details={}. Текст message, крім фіксованого NOT_FOUND, не порівнюється дослівно. Немає паролів/хешів, токенів сесій, чужих контактів, службових причин, особистих даних адміністратора, стеків, SQL або віддзеркалених значень. Єдиний дозволений токен у помилці — новий priceConfirmationToken усередині PRICE_CHANGED.quote.

Назви REQ пояснюють порушення або контекст операції, а не доводять формальне покриття всіх гілок вимоги. Якщо тип/синтаксис/маршрутизацію уточнено лише API-контрактом, це зазначено в передумовах; нових REQ-ID не створюємо. Коди беруться виключно з error-model.md та наявних responses.

## Команди для майбутнього показу помилок у mock

Визначення функції та всі команди нижче **підготовлені, не запущені**. Виконувати від кореня репозиторію після запуску mock. На відміну від позитивної функції, ця зчитує статус, заголовки й тіло також для неуспішних відповідей у Windows PowerShell 5.1. Функція не реалізує авторизацію, бізнес-правила чи сервер. Тіло запиту-носія читає з components/examples поточного OpenAPI.

```powershell
function Invoke-NegativeMock {
    param(
        [string]$Method,
        [string]$Path,
        [int]$Status,
        [ValidateSet('guest', 'client', 'administrator')][string]$Role = 'guest',
        [string]$Example,
        [string]$RequestExample
    )
    $mockHeaders = @{ Accept = 'application/json'; Prefer = "code=$Status, example=$Example" }
    if ($Role -ne 'guest') { $mockHeaders.Authorization = "Bearer mock-$Role" }
    $mockArguments = @{
        UseBasicParsing = $true
        Method = $Method
        Uri = 'http://127.0.0.1:4010/api/v1' + $Path
        Headers = $mockHeaders
    }
    if ($RequestExample) {
        $mockBody = & './.venv-api-validation/Scripts/python.exe' -c "import json,sys,yaml; from pathlib import Path; s=yaml.safe_load(Path('api/openapi.yaml').read_text(encoding='utf-8')); print(json.dumps(s['components']['examples'][sys.argv[1]]['value'], ensure_ascii=True))" $RequestExample
        if ($LASTEXITCODE -ne 0) { throw 'Cannot load the OpenAPI request example.' }
        $mockArguments.ContentType = 'application/json'
        $mockArguments.Body = [System.Text.Encoding]::UTF8.GetBytes(($mockBody -join "`n"))
    }
    try {
        $mockResponse = Invoke-WebRequest @mockArguments
        [pscustomobject]@{ Status = $mockResponse.StatusCode; Headers = $mockResponse.Headers; Content = $mockResponse.Content }
    } catch {
        $mockResponse = $_.Exception.Response
        if (-not $mockResponse) { throw }
        $mockContent = $_.ErrorDetails.Message
        if (-not $mockContent) {
            if ($mockResponse -is [System.Net.HttpWebResponse]) {
                $mockReader = [System.IO.StreamReader]::new($mockResponse.GetResponseStream())
                try { $mockContent = $mockReader.ReadToEnd() } finally { $mockReader.Dispose() }
            } else {
                $mockContent = $mockResponse.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            }
        }
        [pscustomobject]@{ Status = [int]$mockResponse.StatusCode; Headers = $mockResponse.Headers; Content = $mockContent }
    }
}
```

У mock перевірятимуть лише фактично вибраний статичний статус, схему/основні поля та example. Generic VALIDATION_ERROR містить field="$": це допустимий загальний приклад, але не доказ діагностики конкретного поля з негативного запиту. Наприклад, вимога картки позначити currentPassword стосується майбутньої системи; статичний шаблон не деталізує його. Прикладів із навмисно невалідними request bodies до OpenAPI не додаємо: вони не відповідали б схемам.

Retry-After має відображати залишок початкового блокування в реальній системі; статичний приклад заголовка 900 не доводить відліку. Allow має відповідати запитаному URI; WWW-Authenticate: Bearer потрібний лише для AUTHENTICATION_REQUIRED, не для INVALID_CREDENTIALS або FORBIDDEN. Спеціальна форма власних помилок Prism/gateway не змінює ці вимоги до майбутнього API.

## Автентифікація, ролі та чужі дані

### NEG-001. Гість намагається створити бронювання

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-083, REQ-F-089 |
| Роль і незалежні передумови | Гість, Authorization відсутній. Ресурс і дані запиту допустимі; сесії немає. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-confirmation-example"}`. |
| Очікуваний статус / code / заголовки | 401; error.code=`AUTHENTICATION_REQUIRED`; Content-Type: application/json; WWW-Authenticate: Bearer |
| Перевірки системи | Захищені дані не надаються; запит нічого не змінює. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=401, example=AUTHENTICATION_REQUIRED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 401 -Role client -Example AUTHENTICATION_REQUIRED -RequestExample BookingCreateRequest
```

### NEG-002. Власний профіль без автентифікації

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-06; REQ-F-089 |
| Роль і незалежні передумови | Гість, Authorization відсутній. Ресурс і дані запиту допустимі; сесії немає. |
| Негативний запит до майбутньої системи | `GET /api/v1/profile`. Без тіла. |
| Очікуваний статус / code / заголовки | 401; error.code=`AUTHENTICATION_REQUIRED`; Content-Type: application/json; WWW-Authenticate: Bearer |
| Перевірки системи | Захищені дані не надаються; запит нічого не змінює. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/profile`; role=client; без тіла. `Prefer: code=401, example=AUTHENTICATION_REQUIRED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/profile' -Status 401 -Role client -Example AUTHENTICATION_REQUIRED
```

### NEG-003. Перелік бронювань без автентифікації

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-11; REQ-F-089 |
| Роль і незалежні передумови | Гість, Authorization відсутній. Ресурс і дані запиту допустимі; сесії немає. |
| Негативний запит до майбутньої системи | `GET /api/v1/bookings`. Без тіла. |
| Очікуваний статус / code / заголовки | 401; error.code=`AUTHENTICATION_REQUIRED`; Content-Type: application/json; WWW-Authenticate: Bearer |
| Перевірки системи | Захищені дані не надаються; запит нічого не змінює. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/bookings`; role=client; без тіла. `Prefer: code=401, example=AUTHENTICATION_REQUIRED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/bookings' -Status 401 -Role client -Example AUTHENTICATION_REQUIRED
```

### NEG-004. Службовий період без автентифікації

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-19; REQ-F-089 |
| Роль і незалежні передумови | Гість, Authorization відсутній. Ресурс і дані запиту допустимі; сесії немає. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/service-unavailabilities/period-example`. Без тіла. |
| Очікуваний статус / code / заголовки | 401; error.code=`AUTHENTICATION_REQUIRED`; Content-Type: application/json; WWW-Authenticate: Bearer |
| Перевірки системи | Захищені дані не надаються; запит нічого не змінює. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; без тіла. `Prefer: code=401, example=AUTHENTICATION_REQUIRED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/service-unavailabilities/period-example' -Status 401 -Role administrator -Example AUTHENTICATION_REQUIRED
```

### NEG-005. Недійсний Bearer під час зміни профілю

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-07; REQ-F-086, REQ-F-089 |
| Роль і незалежні передумови | К; Authorization: Bearer invalid-session. Неіснуючий токен сесії; це не перевірка невизначеного строку сесії. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/profile`. JSON: `{"phone":"+380671234567"}`. |
| Очікуваний статус / code / заголовки | 401; error.code=`AUTHENTICATION_REQUIRED`; Content-Type: application/json; WWW-Authenticate: Bearer |
| Перевірки системи | Немає пояснення, чому саме токен не прийнято; профіль незмінний. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/profile`; role=client; request example=`ProfilePatch`. `Prefer: code=401, example=AUTHENTICATION_REQUIRED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/profile' -Status 401 -Role client -Example AUTHENTICATION_REQUIRED -RequestExample ProfilePatch
```

### NEG-006. Клієнт читає адміністративний автопарк

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-14; REQ-F-087, REQ-F-089 |
| Роль і незалежні передумови | Клієнт. Чинна сесія цієї ролі; ресурс існує, бізнес-умови й схема запиту допустимі, порушено лише роль. |
| Негативний запит до майбутньої системи | `GET /api/v1/admin/cars`. Без тіла. |
| Очікуваний статус / code / заголовки | 403; error.code=`FORBIDDEN`; Content-Type: application/json; WWW-Authenticate не вимагається, сесія чинна |
| Перевірки системи | Жодної зміни даних; службові причини й чужі контакти відсутні. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/admin/cars`; role=administrator; без тіла. `Prefer: code=403, example=FORBIDDEN`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/admin/cars' -Status 403 -Role administrator -Example FORBIDDEN
```

### NEG-007. Клієнт додає автомобіль

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-15; REQ-F-065, REQ-F-087, REQ-F-089 |
| Роль і незалежні передумови | Клієнт. Чинна сесія цієї ролі; ресурс існує, бізнес-умови й схема запиту допустимі, порушено лише роль. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars`. JSON: `{"characteristics":{"Марка":"Porsche","Модель":"911"},"dailyRate":"1500.00"}`. |
| Очікуваний статус / code / заголовки | 403; error.code=`FORBIDDEN`; Content-Type: application/json; WWW-Authenticate не вимагається, сесія чинна |
| Перевірки системи | Жодної зміни даних; службові причини й чужі контакти відсутні. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars`; role=administrator; request example=`CarCreateRequest`. `Prefer: code=403, example=FORBIDDEN`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars' -Status 403 -Role administrator -Example FORBIDDEN -RequestExample CarCreateRequest
```

### NEG-008. Клієнт приховує авто

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-16; REQ-F-068, REQ-F-087, REQ-F-089 |
| Роль і незалежні передумови | Клієнт. Чинна сесія цієї ролі; ресурс існує, бізнес-умови й схема запиту допустимі, порушено лише роль. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example`. JSON: `{"hidden":true}`. |
| Очікуваний статус / code / заголовки | 403; error.code=`FORBIDDEN`; Content-Type: application/json; WWW-Authenticate не вимагається, сесія чинна |
| Перевірки системи | Жодної зміни даних; службові причини й чужі контакти відсутні. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example`; role=administrator; request example=`CarPatch`. `Prefer: code=403, example=FORBIDDEN`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example' -Status 403 -Role administrator -Example FORBIDDEN -RequestExample CarPatch
```

### NEG-009. Клієнт читає службові причини

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-18; REQ-F-087, REQ-F-089, REQ-F-092 |
| Роль і незалежні передумови | Клієнт. Чинна сесія цієї ролі; ресурс існує, бізнес-умови й схема запиту допустимі, порушено лише роль. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/service-unavailabilities`. Без тіла. |
| Очікуваний статус / code / заголовки | 403; error.code=`FORBIDDEN`; Content-Type: application/json; WWW-Authenticate не вимагається, сесія чинна |
| Перевірки системи | Жодної зміни даних; службові причини й чужі контакти відсутні. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/service-unavailabilities`; role=administrator; без тіла. `Prefer: code=403, example=FORBIDDEN`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/service-unavailabilities' -Status 403 -Role administrator -Example FORBIDDEN
```

### NEG-010. Адміністратор створює бронювання клієнта

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-090, REQ-F-089 |
| Роль і незалежні передумови | Адміністратор. Чинна сесія цієї ролі; ресурс існує, бізнес-умови й схема запиту допустимі, порушено лише роль. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-confirmation-example"}`. |
| Очікуваний статус / code / заголовки | 403; error.code=`FORBIDDEN`; Content-Type: application/json; WWW-Authenticate не вимагається, сесія чинна |
| Перевірки системи | Жодної зміни даних; службові причини й чужі контакти відсутні. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=403, example=FORBIDDEN`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 403 -Role client -Example FORBIDDEN -RequestExample BookingCreateRequest
```

### NEG-011. Клієнт читає чуже бронювання

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-12; REQ-F-084, REQ-F-089, REQ-F-091 |
| Роль і незалежні передумови | Клієнт. booking-other існує й належить іншому К; власна сесія чинна. |
| Негативний запит до майбутньої системи | `GET /api/v1/bookings/booking-other`. Без тіла. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | Тіло повністю таке саме, як для відсутнього бронювання: NOT_FOUND, «Ресурс не знайдено.», details={}; без ознак існування чи власника. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/bookings/booking-example`; role=client; без тіла. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/bookings/booking-example' -Status 404 -Role client -Example NOT_FOUND
```

### NEG-012. Клієнт скасовує чуже бронювання

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-085, REQ-F-089 |
| Роль і незалежні передумови | Клієнт. booking-other — чуже confirmed; часові умови скасування дотримані, щоб ізолювати власність. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-other/cancellation`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | Такий самий 404, як для відсутнього; стан, автор і доступність не змінюються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=client; request example=`ClientCancellationRequest`. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 404 -Role client -Example NOT_FOUND -RequestExample ClientCancellationRequest
```

## Форма запитів, обов’язкові й зайві поля

### NEG-013. Тариф передано числом замість рядка

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-15; REQ-F-065 |
| Роль і незалежні передумови | Адміністратор. Дозволена роль; порушено лише тип dailyRate, визначений API-схемою. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars`. JSON: `{"characteristics":{"Марка":"Porsche","Модель":"911"},"dailyRate":1500}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає dailyRate; авто не створено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars`; role=administrator; request example=`CarCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample CarCreateRequest
```

### NEG-014. Відсутнє обов’язкове ім’я реєстрації

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-04; REQ-F-009 |
| Роль і незалежні передумови | Гість. Email вільний; решта полів допустимі. |
| Негативний запит до майбутньої системи | `POST /api/v1/clients`. JSON: `{"lastName":"Коваль","email":"client@example.com","phone":"+380501234567","password":"ExamplePass8 "}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає firstName; обліковий запис не створено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/clients`; role=guest; request example=`RegistrationRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/clients' -Status 422 -Role guest -Example VALIDATION_ERROR -RequestExample RegistrationRequest
```

### NEG-015. Вхід без обов’язкового email

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-05; REQ-F-012 |
| Роль і незалежні передумови | Гість до входу. Перевіряється схема, а не неправильні облікові дані. |
| Негативний запит до майбутньої системи | `POST /api/v1/sessions`. JSON: `{"password":"ExamplePass8 "}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає email; не INVALID_CREDENTIALS. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/sessions`; role=guest; request example=`LoginRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/sessions' -Status 422 -Role guest -Example VALIDATION_ERROR -RequestExample LoginRequest
```

### NEG-016. Спроба задати роль при реєстрації

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-04; REQ-F-082, REQ-F-089 |
| Роль і незалежні передумови | Гість. Усі дозволені поля коректні; role є невідомим полем запиту. |
| Негативний запит до майбутньої системи | `POST /api/v1/clients`. JSON: `{"firstName":"Олена","lastName":"Коваль","email":"client@example.com","phone":"+380501234567","password":"ExamplePass8 ","role":"administrator"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає role; адміністратора й клієнта цим запитом не створено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/clients`; role=guest; request example=`RegistrationRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/clients' -Status 422 -Role guest -Example VALIDATION_ERROR -RequestExample RegistrationRequest
```

### NEG-017. Спроба вибрати іншого власника бронювання

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-026, REQ-F-089, REQ-F-090 |
| Роль і незалежні передумови | Клієнт. Дозволена клієнтська сесія, авто/період/токен допустимі; зайве clientId не приймається. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-confirmation-example","clientId":"client-other"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає clientId; запису для себе або іншого клієнта не створено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample BookingCreateRequest
```

### NEG-018. Спроба змінити email профілю

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-07; REQ-F-023, REQ-F-089 |
| Роль і незалежні передумови | Клієнт. Власний профіль; email не входить до дозволених полів PATCH. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/profile`. JSON: `{"email":"new@example.com"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає email; початкова адреса незмінна. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/profile`; role=client; request example=`ProfilePatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/profile' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample ProfilePatch
```

### NEG-019. Спроба підмінити профіль через clientId

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-07; REQ-F-086, REQ-F-089 |
| Роль і незалежні передумови | Клієнт. У маршруті /profile власник визначається сесією; довільного clientId у тілі немає. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/profile`. JSON: `{"clientId":"client-other","phone":"+380671234567"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає clientId; чужий профіль незмінний. Не вигадується маршрут редагування /clients/{id}. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/profile`; role=client; request example=`ProfilePatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/profile' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample ProfilePatch
```

### NEG-020. Порожній PATCH профілю

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-07; REQ-F-021 |
| Роль і незалежні передумови | Клієнт. Роль дозволена; власний профіль існує. Порушено погоджену minProperties=1. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/profile`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields містить $ для помилки всього тіла; дані не змінено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/profile`; role=client; request example=`ProfilePatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/profile' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample ProfilePatch
```

### NEG-021. Порожній PATCH авто

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-16; REQ-F-066 |
| Роль і незалежні передумови | Адміністратор. Роль дозволена; автомобіль існує. Порушено погоджену minProperties=1. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields містить $ для помилки всього тіла; дані не змінено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example`; role=administrator; request example=`CarPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample CarPatch
```

### NEG-022. Порожній PATCH службового періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-21; REQ-F-075 |
| Роль і незалежні передумови | Адміністратор. Роль дозволена; ресурс існує; для службового періоду початок ще не настав. Порушено погоджену minProperties=1. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields містить $ для помилки всього тіла; дані не змінено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; request example=`ServicePeriodPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example/service-unavailabilities/period-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample ServicePeriodPatch
```

### NEG-023. Профіль: пробільне firstName

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-07; REQ-F-021 |
| Роль і незалежні передумови | Клієнт. Власний профіль; рядок не містить жодного непробільного символу. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/profile`. JSON: `{"firstName":" \t "}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає firstName; значення не копіюється до помилки. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/profile`; role=client; request example=`ProfilePatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/profile' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample ProfilePatch
```

### NEG-024. Профіль: пробільне phone

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-07; REQ-F-021 |
| Роль і незалежні передумови | Клієнт. Власний профіль; рядок не містить жодного непробільного символу. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/profile`. JSON: `{"phone":" \t "}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає phone; значення не копіюється до помилки. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/profile`; role=client; request example=`ProfilePatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/profile' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample ProfilePatch
```

### NEG-025. Порожній словник характеристик

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-16; REQ-F-066 |
| Роль і незалежні передумови | Адміністратор. Авто існує; characteristics порушує minProperties=1. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example`. JSON: `{"characteristics":{}}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає characteristics; старий словник збережено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example`; role=administrator; request example=`CarPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample CarPatch
```

### NEG-026. Пробільна назва характеристики

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-16; REQ-F-066 |
| Роль і незалежні передумови | Адміністратор. Порушено погоджене NonEmptyString, решта даних допустимі. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example`. JSON: `{"characteristics":{" ":"Porsche"}}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields безпечно позначає characteristics; довільний ключ і значення не віддзеркалюються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example`; role=administrator; request example=`CarPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample CarPatch
```

### NEG-027. Пробільне значення характеристики

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-16; REQ-F-066 |
| Роль і незалежні передумови | Адміністратор. Порушено погоджене NonEmptyString, решта даних допустимі. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example`. JSON: `{"characteristics":{"Марка":" \t"}}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields безпечно позначає characteristics; довільний ключ і значення не віддзеркалюються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example`; role=administrator; request example=`CarPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample CarPatch
```

### NEG-028. Нульовий тариф

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-16; REQ-F-067 |
| Роль і незалежні передумови | Адміністратор. Порушено погоджені проєктні обмеження DailyRate; верхньої межі не вводимо. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example`. JSON: `{"dailyRate":"0.00"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає dailyRate; немає мовчазного округлення чи зміни старого тарифу. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example`; role=administrator; request example=`CarPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample CarPatch
```

### NEG-029. Від’ємний тариф

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-16; REQ-F-067 |
| Роль і незалежні передумови | Адміністратор. Порушено погоджені проєктні обмеження DailyRate; верхньої межі не вводимо. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example`. JSON: `{"dailyRate":"-1.00"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає dailyRate; немає мовчазного округлення чи зміни старого тарифу. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example`; role=administrator; request example=`CarPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample CarPatch
```

### NEG-030. Більше двох десяткових знаків

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-16; REQ-F-067 |
| Роль і незалежні передумови | Адміністратор. Порушено погоджені проєктні обмеження DailyRate; верхньої межі не вводимо. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example`. JSON: `{"dailyRate":"1500.001"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає dailyRate; немає мовчазного округлення чи зміни старого тарифу. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example`; role=administrator; request example=`CarPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample CarPatch
```

### NEG-031. Новий пароль коротший за 8 символів

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-04; REQ-F-014 |
| Роль і незалежні передумови | Гість. Email вільний, дозволені реєстраційні дані допустимі, пароль має 7 символів. |
| Негативний запит до майбутньої системи | `POST /api/v1/clients`. JSON: `{"firstName":"Олена","lastName":"Коваль","email":"client@example.com","phone":"+380501234567","password":"Abc1234"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає password, без його значення; обліковий запис не створено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/clients`; role=guest; request example=`RegistrationRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/clients' -Status 422 -Role guest -Example VALIDATION_ERROR -RequestExample RegistrationRequest
```

### NEG-032. Неправильний поточний пароль

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-08; REQ-F-022 |
| Роль і незалежні передумови | Клієнт. Сесія чинна, newPassword допустимий, currentPassword не відповідає запису. |
| Негативний запит до майбутньої системи | `PUT /api/v1/profile/password`. JSON: `{"currentPassword":"WrongCurrent8","newPassword":"NewExamplePass9 "}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає currentPassword без значення; пароль не змінюється, 401 Bearer тут не застосовується. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PUT /api/v1/profile/password`; role=client; request example=`PasswordChangeRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PUT -Path '/profile/password' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample PasswordChangeRequest
```

### NEG-033. Некоректний синтаксис JSON

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-04; REQ-F-009 |
| Роль і незалежні передумови | Гість. Content-Type: application/json; наведений запит неможливо розібрати як JSON. |
| Негативний запит до майбутньої системи | `POST /api/v1/clients`. Нерозбірний сирий JSON: `{"firstName":`. |
| Очікуваний статус / code / заголовки | 400; error.code=`BAD_REQUEST`; Content-Type: application/json |
| Перевірки системи | details={}; без парсера, винятків чи фрагмента введеного тіла у відповіді. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/clients`; role=guest; request example=`RegistrationRequest`. `Prefer: code=400, example=BAD_REQUEST`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/clients' -Status 400 -Role guest -Example BAD_REQUEST -RequestExample RegistrationRequest
```

## Періоди, календарні дати й часові обмеження

### NEG-034. Пошук лише з однією межею

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-01; REQ-F-004 |
| Роль і незалежні передумови | Гість. Пошук доступних авто; endsAt відсутнє, каталог без обох меж тут не запитується. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars?startsAt=2026-11-12T09`. Без тіла. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує відсутню межу endsAt; пошук не виконується. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars?startsAt=2026-11-12T09&endsAt=2026-11-14T09`; role=guest; без тіла. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 422 -Role guest -Example VALIDATION_ERROR
```

### NEG-035. LocalHour містить хвилини в рядку

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-03; REQ-F-027 |
| Роль і незалежні передумови | Гість. Неприховане car-example існує; перевіряється лише валідність меж. Для пошуку немає обмежень майбутності, 1–30/90. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09:00&endsAt=2026-11-14T09`. Без тіла. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | Структура YYYY-MM-DDTHH порушена, навіть якщо хвилини 00. fields указує відповідну межу; без службових причин. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`; role=guest; без тіла. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 422 -Role guest -Example VALIDATION_ERROR
```

### NEG-036. Неіснуюча календарна дата

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-03; REQ-F-028 |
| Роль і незалежні передумови | Гість. Неприховане car-example існує; перевіряється лише валідність меж. Для пошуку немає обмежень майбутності, 1–30/90. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/availability?startsAt=2026-02-30T09&endsAt=2026-03-02T09`. Без тіла. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | Шаблон компонентів сам по собі допускає 30 лютого; сервер має відхилити неіснуючу дату. fields указує відповідну межу; без службових причин. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`; role=guest; без тіла. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 422 -Role guest -Example VALIDATION_ERROR
```

### NEG-037. Завершення раніше початку

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-03; REQ-F-006 |
| Роль і незалежні передумови | Гість. Неприховане car-example існує; перевіряється лише валідність меж. Для пошуку немає обмежень майбутності, 1–30/90. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/availability?startsAt=2026-11-14T09&endsAt=2026-11-12T09`. Без тіла. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | Сервер відхиляє endsAt < startsAt. fields указує відповідну межу; без службових причин. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`; role=guest; без тіла. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 422 -Role guest -Example VALIDATION_ERROR
```

### NEG-038. Нульовий період перевірки доступності

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-03; REQ-F-006 |
| Роль і незалежні передумови | Гість. Неприховане car-example існує; перевіряється лише валідність меж. Для пошуку немає обмежень майбутності, 1–30/90. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-12T09`. Без тіла. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | Сервер відхиляє endsAt = startsAt. fields указує відповідну межу; без службових причин. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`; role=guest; без тіла. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 422 -Role guest -Example VALIDATION_ERROR
```

### NEG-039. Неіснуюча місцева година Europe/Kyiv

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-03; REQ-F-028, REQ-F-029 |
| Роль і незалежні передумови | Гість. Неприховане car-example існує; перевіряється лише валідність меж. Для пошуку немає обмежень майбутності, 1–30/90. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/availability?startsAt=2026-03-29T03&endsAt=2026-03-30T03`. Без тіла. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | Для введеної межі немає відповідного моменту; автоматичне перенесення як у межі скасування не застосовується. fields указує відповідну межу; без службових причин. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`; role=guest; без тіла. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 422 -Role guest -Example VALIDATION_ERROR
```

### NEG-040. Неоднозначна місцева година Europe/Kyiv

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-03; REQ-F-028, REQ-F-030 |
| Роль і незалежні передумови | Гість. Неприховане car-example існує; перевіряється лише валідність меж. Для пошуку немає обмежень майбутності, 1–30/90. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/availability?startsAt=2026-10-25T03&endsAt=2026-10-26T03`. Без тіла. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | Введена межа має два входження; сервер не обирає одне мовчки. fields указує відповідну межу; без службових причин. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`; role=guest; без тіла. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 422 -Role guest -Example VALIDATION_ERROR
```

### NEG-041. Розрахунок із початком у поточний момент

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-09; REQ-F-031 |
| Роль і незалежні передумови | Клієнт. Контрольований час 2026-11-10T12:00:00+02:00; car-example доступне, інші правила дотримані. |
| Негативний запит до майбутньої системи | `POST /api/v1/booking-quotes`. JSON: `{"carId":"car-example","startsAt":"2026-11-10T12","endsAt":"2026-11-12T12"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує порушення періоду; Quote/priceConfirmationToken не видаються; фіксовані 24 години замість календарних діб не використовуються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/booking-quotes`; role=client; request example=`QuoteRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/booking-quotes' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample QuoteRequest
```

### NEG-042. Оренда коротша за календарну добу

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-09; REQ-F-032, REQ-F-035 |
| Роль і незалежні передумови | Клієнт. Контрольований час 2026-11-10T12:00:00+02:00; car-example доступне, інші правила дотримані. |
| Негативний запит до майбутньої системи | `POST /api/v1/booking-quotes`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-13T08"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує порушення періоду; Quote/priceConfirmationToken не видаються; фіксовані 24 години замість календарних діб не використовуються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/booking-quotes`; role=client; request example=`QuoteRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/booking-quotes' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample QuoteRequest
```

### NEG-043. Оренда довша за 30 календарних діб

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-09; REQ-F-033, REQ-F-035 |
| Роль і незалежні передумови | Клієнт. Контрольований час 2026-11-10T12:00:00+02:00; car-example доступне, інші правила дотримані. |
| Негативний запит до майбутньої системи | `POST /api/v1/booking-quotes`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-12-12T10"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує порушення періоду; Quote/priceConfirmationToken не видаються; фіксовані 24 години замість календарних діб не використовуються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/booking-quotes`; role=client; request example=`QuoteRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/booking-quotes' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample QuoteRequest
```

### NEG-044. Початок на годину за 90-денним горизонтом

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-09; REQ-F-034, REQ-F-035 |
| Роль і незалежні передумови | Клієнт. Контрольований час 2026-11-10T12:00:00+02:00; car-example доступне, інші правила дотримані. |
| Негативний запит до майбутньої системи | `POST /api/v1/booking-quotes`. JSON: `{"carId":"car-example","startsAt":"2027-02-08T13","endsAt":"2027-02-09T13"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує порушення періоду; Quote/priceConfirmationToken не видаються; фіксовані 24 години замість календарних діб не використовуються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/booking-quotes`; role=client; request example=`QuoteRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/booking-quotes' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample QuoteRequest
```

### NEG-045. Початок настав після отримання токена ціни

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-031, REQ-F-040 |
| Роль і незалежні передумови | Клієнт. Час 2026-11-10T12:00:00+02:00; токен видано раніше для тоді майбутнього початку 2026-11-10T12. Він відповідає цьому клієнту/авто/періоду й тарифу; доступність збережена. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-10T12","endsAt":"2026-11-12T12","priceConfirmationToken":"previously-issued-price-token"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | Повторна перевірка початку відхиляє запис; бронювання не створено. Строк токена ціни або сесії не вигадується. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample BookingCreateRequest
```

## Доступність, ціна й токен підтвердження

### NEG-046. Розрахунок: авто зайняте підтвердженим бронюванням

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-09; REQ-F-007 |
| Роль і незалежні передумови | Клієнт. Період і роль допустимі, тариф незмінний; авто зайняте підтвердженим бронюванням.  |
| Негативний запит до майбутньої системи | `POST /api/v1/booking-quotes`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`CAR_UNAVAILABLE`; Content-Type: application/json |
| Перевірки системи | details={}; жодних записів бронювань цим запитом не створено; немає причин недоступності або чужих даних. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/booking-quotes`; role=client; request example=`QuoteRequest`. `Prefer: code=409, example=CAR_UNAVAILABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/booking-quotes' -Status 409 -Role client -Example CAR_UNAVAILABLE -RequestExample QuoteRequest
```

### NEG-047. Розрахунок: авто приховане

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-09; REQ-F-007 |
| Роль і незалежні передумови | Клієнт. Період і роль допустимі, тариф незмінний; авто приховане.  |
| Негативний запит до майбутньої системи | `POST /api/v1/booking-quotes`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`CAR_UNAVAILABLE`; Content-Type: application/json |
| Перевірки системи | details={}; жодних записів бронювань цим запитом не створено; немає причин недоступності або чужих даних. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/booking-quotes`; role=client; request example=`QuoteRequest`. `Prefer: code=409, example=CAR_UNAVAILABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/booking-quotes' -Status 409 -Role client -Example CAR_UNAVAILABLE -RequestExample QuoteRequest
```

### NEG-048. Розрахунок: авто перетинає службовий період

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-09; REQ-F-007, REQ-F-092 |
| Роль і незалежні передумови | Клієнт. Період і роль допустимі, тариф незмінний; авто перетинає службовий період.  |
| Негативний запит до майбутньої системи | `POST /api/v1/booking-quotes`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`CAR_UNAVAILABLE`; Content-Type: application/json |
| Перевірки системи | details={}; жодних записів бронювань цим запитом не створено; немає причин недоступності або чужих даних. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/booking-quotes`; role=client; request example=`QuoteRequest`. `Prefer: code=409, example=CAR_UNAVAILABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/booking-quotes' -Status 409 -Role client -Example CAR_UNAVAILABLE -RequestExample QuoteRequest
```

### NEG-049. Бронювання: авто зайняте іншим успішним конкурентним запитом

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-007, REQ-F-041, REQ-F-042 |
| Роль і незалежні передумови | Клієнт. Період і роль допустимі, тариф незмінний; авто зайняте іншим успішним конкурентним запитом. Токен отримано, коли авто ще було доступним; перед запитом стан змінився. Інший запит або приховування задані фікстурою, не попереднім NEG. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-confirmation-example"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`CAR_UNAVAILABLE`; Content-Type: application/json |
| Перевірки системи | details={}; жодних записів бронювань цим запитом не створено; немає причин недоступності або чужих даних. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=409, example=CAR_UNAVAILABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 409 -Role client -Example CAR_UNAVAILABLE -RequestExample BookingCreateRequest
```

### NEG-050. Бронювання: авто приховане після показу ціни

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-007, REQ-F-042 |
| Роль і незалежні передумови | Клієнт. Період і роль допустимі, тариф незмінний; авто приховане після показу ціни. Токен отримано, коли авто ще було доступним; перед запитом стан змінився. Інший запит або приховування задані фікстурою, не попереднім NEG. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-confirmation-example"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`CAR_UNAVAILABLE`; Content-Type: application/json |
| Перевірки системи | details={}; жодних записів бронювань цим запитом не створено; немає причин недоступності або чужих даних. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=409, example=CAR_UNAVAILABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 409 -Role client -Example CAR_UNAVAILABLE -RequestExample BookingCreateRequest
```

### NEG-051. Тариф змінився після показу ціни

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-039, REQ-F-043 |
| Роль і незалежні передумови | Клієнт. К має раніше виданий токен ціни 1500.00 × 2; до поточного запиту тариф змінено на 1800.00. Авто доступне, період допустимий. Усе підготовлено фікстурою. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-confirmation-example"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`PRICE_CHANGED`; Content-Type: application/json |
| Перевірки системи | details.quote за схемою Quote: dailyRate="1800.00", billableDays=2, totalPrice="3600.00", новий priceConfirmationToken; carId/період ті самі, UAH. Бронювання ще не створено, потрібне окреме повторне підтвердження; accessToken відсутній. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=409, example=PRICE_CHANGED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 409 -Role client -Example PRICE_CHANGED -RequestExample BookingCreateRequest
```

### NEG-052. Невалідний токен ціни

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-039, REQ-F-040 |
| Роль і незалежні передумови | Клієнт. Токен має правильний тип непорожнього рядка, але сервер його не визнає; інші дані й доступність допустимі. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"invalid-price-token"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає priceConfirmationToken без значення й причин криптографічної перевірки; запис не створено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample BookingCreateRequest
```

### NEG-053. Токен ціни належить іншому клієнту

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-039, REQ-F-040 |
| Роль і незалежні передумови | Клієнт. Підготовлений раніше токен коректний як запис, але відповідає іншому клієнту; поточні авто/період доступні й допустимі. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-token-for-other-context"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає priceConfirmationToken без даних його власника/контексту; жодного бронювання. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample BookingCreateRequest
```

### NEG-054. Токен ціни належить іншому автомобілю

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-039, REQ-F-040 |
| Роль і незалежні передумови | Клієнт. Підготовлений раніше токен коректний як запис, але відповідає іншому автомобілю; поточні авто/період доступні й допустимі. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-token-for-other-context"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає priceConfirmationToken без даних його власника/контексту; жодного бронювання. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample BookingCreateRequest
```

### NEG-055. Токен ціни належить іншому періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-10; REQ-F-039, REQ-F-040 |
| Роль і незалежні передумови | Клієнт. Підготовлений раніше токен коректний як запис, але відповідає іншому періоду; поточні авто/період доступні й допустимі. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings`. JSON: `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-token-for-other-context"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає priceConfirmationToken без даних його власника/контексту; жодного бронювання. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings`; role=client; request example=`BookingCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample BookingCreateRequest
```

## Реєстрація, облікові дані й тимчасове блокування

### NEG-056. Повторна реєстрація нормалізованого email

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-04; REQ-F-010, REQ-F-011 |
| Роль і незалежні передумови | Гість. Обліковий запис client@example.com уже існує; крайні пробіли прибираються перед перевіркою формату й унікальності, регістр не враховується. |
| Негативний запит до майбутньої системи | `POST /api/v1/clients`. JSON: `{"firstName":"Олена","lastName":"Коваль","email":"  CLIENT@example.com  ","phone":"+380501234567","password":"ExamplePass8 "}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`EMAIL_ALREADY_EXISTS`; Content-Type: application/json |
| Перевірки системи | details={}; другого запису немає; не повертаються чужі ім’я/телефон чи дані облікового запису. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/clients`; role=guest; request example=`RegistrationRequest`. `Prefer: code=409, example=EMAIL_ALREADY_EXISTS`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/clients' -Status 409 -Role guest -Example EMAIL_ALREADY_EXISTS -RequestExample RegistrationRequest
```

### NEG-057. Неправильний пароль входу

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-05; REQ-F-012, REQ-F-013, REQ-F-015 |
| Роль і незалежні передумови | Гість до входу. Блокування немає; для існуючого запису лічильник дорівнює 0, тобто це не п’ята помилка. Для невідомого email факт існування не розкривається. |
| Негативний запит до майбутньої системи | `POST /api/v1/sessions`. JSON: `{"email":"client@example.com","password":"WrongPassword8"}`. |
| Очікуваний статус / code / заголовки | 401; error.code=`INVALID_CREDENTIALS`; Content-Type: application/json; WWW-Authenticate: Bearer не додається (це вхід за email/паролем) |
| Перевірки системи | Спільне пояснення про неправильні email/пароль; details={}, немає токена або даних запису; повідомлення не відрізняє невідому адресу від помилкового пароля. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/sessions`; role=guest; request example=`LoginRequest`. `Prefer: code=401, example=INVALID_CREDENTIALS`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/sessions' -Status 401 -Role guest -Example INVALID_CREDENTIALS -RequestExample LoginRequest
```

### NEG-058. Невідомий email входу

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-05; REQ-F-012, REQ-F-013, REQ-F-015 |
| Роль і незалежні передумови | Гість до входу. Блокування немає; для існуючого запису лічильник дорівнює 0, тобто це не п’ята помилка. Для невідомого email факт існування не розкривається. |
| Негативний запит до майбутньої системи | `POST /api/v1/sessions`. JSON: `{"email":"unknown@example.com","password":"WrongPassword8"}`. |
| Очікуваний статус / code / заголовки | 401; error.code=`INVALID_CREDENTIALS`; Content-Type: application/json; WWW-Authenticate: Bearer не додається (це вхід за email/паролем) |
| Перевірки системи | Спільне пояснення про неправильні email/пароль; details={}, немає токена або даних запису; повідомлення не відрізняє невідому адресу від помилкового пароля. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/sessions`; role=guest; request example=`LoginRequest`. `Prefer: code=401, example=INVALID_CREDENTIALS`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/sessions' -Status 401 -Role guest -Example INVALID_CREDENTIALS -RequestExample LoginRequest
```

### NEG-059. П’ята послідовна помилка входу клієнта

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-05; REQ-F-015, REQ-F-016, REQ-F-017 |
| Роль і незалежні передумови | Гість, обліковий запис К. У незалежній фікстурі рівно 4 попередні послідовні помилки цього запису, блокування ще немає. Поточний пароль неправильний. |
| Негативний запит до майбутньої системи | `POST /api/v1/sessions`. JSON: `{"email":"client@example.com","password":"WrongPassword8"}`. |
| Очікуваний статус / code / заголовки | 429; error.code=`LOGIN_BLOCKED`; Content-Type: application/json; Retry-After: додатне ціле секунд до початкової межі |
| Перевірки системи | Запускається 15-хвилинне блокування лише цього запису, Retry-After близько 900 секунд на момент відповіді; токен не видається. Попередні спроби тут не виконуються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/sessions`; role=guest; request example=`LoginRequest`. `Prefer: code=429, example=LOGIN_BLOCKED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/sessions' -Status 429 -Role guest -Example LOGIN_BLOCKED -RequestExample LoginRequest
```

### NEG-060. Правильний пароль під час блокування клієнта

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-05; REQ-F-016, REQ-F-017, REQ-F-018 |
| Роль і незалежні передумови | Гість до входу, запис К. Блокування зафіксовано з 11:55 до 12:10; контрольований час 12:00 тієї самої доби. Правильний пароль не обходить блокування, повторна спроба не переносить його межу. |
| Негативний запит до майбутньої системи | `POST /api/v1/sessions`. JSON: `{"email":"client@example.com","password":"ExamplePass8 "}`. |
| Очікуваний статус / code / заголовки | 429; error.code=`LOGIN_BLOCKED`; Content-Type: application/json; Retry-After: додатне ціле секунд до початкової межі |
| Перевірки системи | Retry-After — додатний залишок до початкової межі (приблизно 600 с для цієї фікстури), details={}, токена немає. Mock може видати статичний заголовок 900 і не доводить відлік. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/sessions`; role=guest; request example=`LoginRequest`. `Prefer: code=429, example=LOGIN_BLOCKED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/sessions' -Status 429 -Role guest -Example LOGIN_BLOCKED -RequestExample LoginRequest
```

### NEG-061. Правильний пароль під час блокування адміністратора

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-05; REQ-F-016, REQ-F-017, REQ-F-018 |
| Роль і незалежні передумови | Гість до входу, запис А. Блокування зафіксовано з 11:55 до 12:10; контрольований час 12:00 тієї самої доби. Правильний пароль не обходить блокування, повторна спроба не переносить його межу. |
| Негативний запит до майбутньої системи | `POST /api/v1/sessions`. JSON: `{"email":"admin@example.com","password":"ExamplePass8 "}`. |
| Очікуваний статус / code / заголовки | 429; error.code=`LOGIN_BLOCKED`; Content-Type: application/json; Retry-After: додатне ціле секунд до початкової межі |
| Перевірки системи | Retry-After — додатний залишок до початкової межі (приблизно 600 с для цієї фікстури), details={}, токена немає. Mock може видати статичний заголовок 900 і не доводить відлік. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/sessions`; role=guest; request example=`LoginAdminRequest`. `Prefer: code=429, example=LOGIN_BLOCKED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/sessions' -Status 429 -Role guest -Example LOGIN_BLOCKED -RequestExample LoginAdminRequest
```

## Недозволене скасування

### NEG-062. Клієнт скасовує після дозволеної межі

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-051, REQ-F-055 |
| Роль і незалежні передумови | Клієнт. Власне confirmed booking-example; початок 2026-11-12T09, межа 2026-11-11T09:00:00+02:00; серверний час на секунду пізніше межі, але до початку. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`CANCELLATION_DEADLINE_PASSED`; Content-Type: application/json |
| Перевірки системи | details={}; бронювання залишається confirmed, період заблоковано, cancellation не створено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=client; request example=`ClientCancellationRequest`. `Prefer: code=409, example=CANCELLATION_DEADLINE_PASSED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 409 -Role client -Example CANCELLATION_DEADLINE_PASSED -RequestExample ClientCancellationRequest
```

### NEG-063. Клієнт скасовує active

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-048, REQ-F-050, REQ-F-059 |
| Роль і незалежні передумови | Клієнт. Стан нескасованого booking-example на контрольований час 2026-11-12T09:00:00+02:00 — active; для К це власне бронювання, для А причина допустима. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`BOOKING_NOT_CANCELLABLE`; Content-Type: application/json |
| Перевірки системи | details={}; збережено відповідний стан і період/ціни; запису скасування немає; не підміняти код на CANCELLATION_DEADLINE_PASSED для вже активного/завершеного. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=client; request example=`ClientCancellationRequest`. `Prefer: code=409, example=BOOKING_NOT_CANCELLABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 409 -Role client -Example BOOKING_NOT_CANCELLABLE -RequestExample ClientCancellationRequest
```

### NEG-064. Адміністратор скасовує active

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-048, REQ-F-050, REQ-F-059 |
| Роль і незалежні передумови | Адміністратор. Стан нескасованого booking-example на контрольований час 2026-11-12T09:00:00+02:00 — active; для К це власне бронювання, для А причина допустима. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{"reason":"Заміна автомобіля в автопарку неможлива."}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`BOOKING_NOT_CANCELLABLE`; Content-Type: application/json |
| Перевірки системи | details={}; збережено відповідний стан і період/ціни; запису скасування немає; не підміняти код на CANCELLATION_DEADLINE_PASSED для вже активного/завершеного. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=administrator; request example=`AdminCancellationRequest`. `Prefer: code=409, example=BOOKING_NOT_CANCELLABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 409 -Role administrator -Example BOOKING_NOT_CANCELLABLE -RequestExample AdminCancellationRequest
```

### NEG-065. Клієнт скасовує completed

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-049, REQ-F-050, REQ-F-059 |
| Роль і незалежні передумови | Клієнт. Стан нескасованого booking-example на контрольований час 2026-11-14T09:00:00+02:00 — completed; для К це власне бронювання, для А причина допустима. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`BOOKING_NOT_CANCELLABLE`; Content-Type: application/json |
| Перевірки системи | details={}; збережено відповідний стан і період/ціни; запису скасування немає; не підміняти код на CANCELLATION_DEADLINE_PASSED для вже активного/завершеного. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=client; request example=`ClientCancellationRequest`. `Prefer: code=409, example=BOOKING_NOT_CANCELLABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 409 -Role client -Example BOOKING_NOT_CANCELLABLE -RequestExample ClientCancellationRequest
```

### NEG-066. Адміністратор скасовує completed

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-049, REQ-F-050, REQ-F-059 |
| Роль і незалежні передумови | Адміністратор. Стан нескасованого booking-example на контрольований час 2026-11-14T09:00:00+02:00 — completed; для К це власне бронювання, для А причина допустима. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{"reason":"Заміна автомобіля в автопарку неможлива."}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`BOOKING_NOT_CANCELLABLE`; Content-Type: application/json |
| Перевірки системи | details={}; збережено відповідний стан і період/ціни; запису скасування немає; не підміняти код на CANCELLATION_DEADLINE_PASSED для вже активного/завершеного. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=administrator; request example=`AdminCancellationRequest`. `Prefer: code=409, example=BOOKING_NOT_CANCELLABLE`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 409 -Role administrator -Example BOOKING_NOT_CANCELLABLE -RequestExample AdminCancellationRequest
```

### NEG-067. Повторне скасування вже скасованого бронювання

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-060, REQ-F-062 |
| Роль і незалежні передумови | Клієнт. Власне бронювання вже cancelled у фікстурі; час/автор першого скасування відомі, часові умови до початку дотримані. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`ALREADY_CANCELLED`; Content-Type: application/json |
| Перевірки системи | details={}; нового запису немає, первинні cancelledAt й автор незмінні. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=client; request example=`ClientCancellationRequest`. `Prefer: code=409, example=ALREADY_CANCELLED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 409 -Role client -Example ALREADY_CANCELLED -RequestExample ClientCancellationRequest
```

### NEG-068. Скасування адміністратором без reason

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-057, REQ-F-058 |
| Роль і незалежні передумови | Адміністратор. Підтверджене бронювання, строго до початку; дозволена роль, порушена лише обов’язкова причина. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує reason або помилку всього тіла $; стан залишається confirmed. Відповідність варіанта requestBody ролі перевіряє сервер, а не лише oneOf. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=administrator; request example=`AdminCancellationRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample AdminCancellationRequest
```

### NEG-069. Пробільна причина адміністративного скасування

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-057, REQ-F-058 |
| Роль і незалежні передумови | Адміністратор. Підтверджене бронювання, строго до початку; дозволена роль, порушена лише обов’язкова причина. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{"reason":" \t "}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує reason або помилку всього тіла $; стан залишається confirmed. Відповідність варіанта requestBody ролі перевіряє сервер, а не лише oneOf. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=administrator; request example=`AdminCancellationRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample AdminCancellationRequest
```

### NEG-070. Адміністративне скасування без тіла

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-057, REQ-F-058 |
| Роль і незалежні передумови | Адміністратор. Підтверджене бронювання, строго до початку; дозволена роль, порушена лише обов’язкова причина. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. Без тіла. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує reason або помилку всього тіла $; стан залишається confirmed. Відповідність варіанта requestBody ролі перевіряє сервер, а не лише oneOf. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=administrator; request example=`AdminCancellationRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample AdminCancellationRequest
```

### NEG-071. Клієнт передає адміністративне поле reason

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-13; REQ-F-056, REQ-F-089 |
| Роль і незалежні передумови | Клієнт. Власне confirmed і дозволений час; клієнтський варіант тіла дозволяє лише {} або відсутнє тіло, а не reason. |
| Негативний запит до майбутньої системи | `POST /api/v1/bookings/booking-example/cancellation`. JSON: `{"reason":"Непотрібна клієнтська причина."}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає reason; це погоджена закритість клієнтського requestBody, не нова обов’язковість причини; стан незмінний. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/bookings/booking-example/cancellation`; role=client; request example=`ClientCancellationRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 422 -Role client -Example VALIDATION_ERROR -RequestExample ClientCancellationRequest
```

## Зв’язки автомобіля та службові періоди

### NEG-072. Видалення авто з історичним бронюванням

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-17; REQ-F-072 |
| Роль і незалежні передумови | Адміністратор. car-example існує й має хоча б одне пов’язане скасоване історичне бронювання; інших перешкод немає. |
| Негативний запит до майбутньої системи | `DELETE /api/v1/cars/car-example`. Без тіла. |
| Очікуваний статус / code / заголовки | 409; error.code=`CAR_HAS_RELATED_RECORDS`; Content-Type: application/json |
| Перевірки системи | details={}; авто й зв’язки зберігаються, у помилці немає історичних контактів чи службової причини. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `DELETE /api/v1/cars/car-example`; role=administrator; без тіла. `Prefer: code=409, example=CAR_HAS_RELATED_RECORDS`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method DELETE -Path '/cars/car-example' -Status 409 -Role administrator -Example CAR_HAS_RELATED_RECORDS
```

### NEG-073. Видалення авто з історичною недоступністю

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-17; REQ-F-072 |
| Роль і незалежні передумови | Адміністратор. car-example існує й має хоча б одне пов’язане історичний службовий період; інших перешкод немає. |
| Негативний запит до майбутньої системи | `DELETE /api/v1/cars/car-example`. Без тіла. |
| Очікуваний статус / code / заголовки | 409; error.code=`CAR_HAS_RELATED_RECORDS`; Content-Type: application/json |
| Перевірки системи | details={}; авто й зв’язки зберігаються, у помилці немає історичних контактів чи службової причини. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `DELETE /api/v1/cars/car-example`; role=administrator; без тіла. `Prefer: code=409, example=CAR_HAS_RELATED_RECORDS`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method DELETE -Path '/cars/car-example' -Status 409 -Role administrator -Example CAR_HAS_RELATED_RECORDS
```

### NEG-074. Службовий період починається не в майбутньому

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-20; REQ-F-073 |
| Роль і незалежні передумови | Адміністратор. Контрольований час 2026-11-10T12:00:00+02:00; початок дорівнює зараз, перетинів немає. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars/car-example/service-unavailabilities`. JSON: `{"startsAt":"2026-11-10T12","endsAt":"2026-11-21T09","reason":"Планове технічне обслуговування."}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає startsAt; службовий період не створено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars/car-example/service-unavailabilities`; role=administrator; request example=`ServicePeriodCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars/car-example/service-unavailabilities' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample ServicePeriodCreateRequest
```

### NEG-075. Завершення службового періоду не після початку

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-20; REQ-F-074 |
| Роль і незалежні передумови | Адміністратор. Обидві введені межі однозначні; порушено погоджений порядок меж, а не ліміти оренди. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars/car-example/service-unavailabilities`. JSON: `{"startsAt":"2026-11-20T09","endsAt":"2026-11-20T09","reason":"Планове технічне обслуговування."}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields указує порушення меж, немає створеного періоду; службова причина не віддзеркалюється. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars/car-example/service-unavailabilities`; role=administrator; request example=`ServicePeriodCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars/car-example/service-unavailabilities' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample ServicePeriodCreateRequest
```

### NEG-076. Створення службової недоступності з перетином із підтвердженим бронюванням

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-20; REQ-F-077, REQ-F-078 |
| Роль і незалежні передумови | Адміністратор. Новий період 2026-11-20T09–2026-11-21T09 перетинається з підтвердженим бронюванням. Початок нового періоду майбутній; решта даних допустимі. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars/car-example/service-unavailabilities`. JSON: `{"startsAt":"2026-11-20T09","endsAt":"2026-11-21T09","reason":"Планове технічне обслуговування."}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`SERVICE_PERIOD_CONFLICT`; Content-Type: application/json |
| Перевірки системи | details={}; службовий період не створено, бронювання не скасовуються; відсутні id конфліктів, контакти й службові причини. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars/car-example/service-unavailabilities`; role=administrator; request example=`ServicePeriodCreateRequest`. `Prefer: code=409, example=SERVICE_PERIOD_CONFLICT`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars/car-example/service-unavailabilities' -Status 409 -Role administrator -Example SERVICE_PERIOD_CONFLICT -RequestExample ServicePeriodCreateRequest
```

### NEG-077. Створення службової недоступності з перетином із активним бронюванням

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-20; REQ-F-077, REQ-F-078 |
| Роль і незалежні передумови | Адміністратор. Новий період 2026-11-20T09–2026-11-21T09 перетинається з активним бронюванням. Час 2026-11-20T08:00:00+02:00; активне бронювання почалося напередодні й завершується 2026-11-20T12, тобто новий початок ще майбутній. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars/car-example/service-unavailabilities`. JSON: `{"startsAt":"2026-11-20T09","endsAt":"2026-11-21T09","reason":"Планове технічне обслуговування."}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`SERVICE_PERIOD_CONFLICT`; Content-Type: application/json |
| Перевірки системи | details={}; службовий період не створено, бронювання не скасовуються; відсутні id конфліктів, контакти й службові причини. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars/car-example/service-unavailabilities`; role=administrator; request example=`ServicePeriodCreateRequest`. `Prefer: code=409, example=SERVICE_PERIOD_CONFLICT`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars/car-example/service-unavailabilities' -Status 409 -Role administrator -Example SERVICE_PERIOD_CONFLICT -RequestExample ServicePeriodCreateRequest
```

### NEG-078. Створення службової недоступності з перетином із іншим службовим періодом

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-20; REQ-F-079 |
| Роль і незалежні передумови | Адміністратор. Новий період 2026-11-20T09–2026-11-21T09 перетинається з іншим службовим періодом. Початок нового періоду майбутній; решта даних допустимі. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars/car-example/service-unavailabilities`. JSON: `{"startsAt":"2026-11-20T09","endsAt":"2026-11-21T09","reason":"Планове технічне обслуговування."}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`SERVICE_PERIOD_CONFLICT`; Content-Type: application/json |
| Перевірки системи | details={}; службовий період не створено, бронювання не скасовуються; відсутні id конфліктів, контакти й службові причини. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars/car-example/service-unavailabilities`; role=administrator; request example=`ServicePeriodCreateRequest`. `Prefer: code=409, example=SERVICE_PERIOD_CONFLICT`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars/car-example/service-unavailabilities' -Status 409 -Role administrator -Example SERVICE_PERIOD_CONFLICT -RequestExample ServicePeriodCreateRequest
```

### NEG-079. Редагування службового періоду з перетином із підтвердженим бронюванням

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-21; REQ-F-075, REQ-F-077, REQ-F-078 |
| Роль і незалежні передумови | Адміністратор. Чинний період 2026-11-20T09–2026-11-21T09 ще не почався. Нове завершення 2026-11-22T09 розширює його на зайнятий проміжок 2026-11-21T12–2026-11-22T12; старий період був безконфліктним. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`. JSON: `{"endsAt":"2026-11-22T09"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`SERVICE_PERIOD_CONFLICT`; Content-Type: application/json |
| Перевірки системи | details={}; старі межі/причина збережені; пов’язане бронювання або інший період не змінено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; request example=`ServicePeriodPatch`. `Prefer: code=409, example=SERVICE_PERIOD_CONFLICT`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example/service-unavailabilities/period-example' -Status 409 -Role administrator -Example SERVICE_PERIOD_CONFLICT -RequestExample ServicePeriodPatch
```

### NEG-080. Редагування службового періоду з перетином із іншим службовим періодом

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-21; REQ-F-075, REQ-F-079 |
| Роль і незалежні передумови | Адміністратор. Чинний період 2026-11-20T09–2026-11-21T09 ще не почався. Нове завершення 2026-11-22T09 розширює його на зайнятий проміжок 2026-11-21T12–2026-11-22T12; старий період був безконфліктним. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`. JSON: `{"endsAt":"2026-11-22T09"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`SERVICE_PERIOD_CONFLICT`; Content-Type: application/json |
| Перевірки системи | details={}; старі межі/причина збережені; пов’язане бронювання або інший період не змінено. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; request example=`ServicePeriodPatch`. `Prefer: code=409, example=SERVICE_PERIOD_CONFLICT`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example/service-unavailabilities/period-example' -Status 409 -Role administrator -Example SERVICE_PERIOD_CONFLICT -RequestExample ServicePeriodPatch
```

### NEG-081. Редагування службового періоду від моменту початку

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-21; REQ-F-075, REQ-F-081 |
| Роль і незалежні передумови | Адміністратор. Чинний період починається 2026-11-20T09; контрольований час рівно 2026-11-20T09:00:00+02:00. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`. JSON: `{"endsAt":"2026-11-22T09"}`. |
| Очікуваний статус / code / заголовки | 409; error.code=`SERVICE_PERIOD_ALREADY_STARTED`; Content-Type: application/json |
| Перевірки системи | details={}; історія й початкові межі/причина незмінні. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; request example=`ServicePeriodPatch`. `Prefer: code=409, example=SERVICE_PERIOD_ALREADY_STARTED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example/service-unavailabilities/period-example' -Status 409 -Role administrator -Example SERVICE_PERIOD_ALREADY_STARTED -RequestExample ServicePeriodPatch
```

### NEG-082. Видалення розпочатого службового періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-22; REQ-F-076, REQ-F-081 |
| Роль і незалежні передумови | Адміністратор. Час рівно 2026-11-20T09:00:00+02:00, тобто початок уже настав. |
| Негативний запит до майбутньої системи | `DELETE /api/v1/cars/car-example/service-unavailabilities/period-example`. Без тіла. |
| Очікуваний статус / code / заголовки | 409; error.code=`SERVICE_PERIOD_ALREADY_STARTED`; Content-Type: application/json |
| Перевірки системи | details={}; період лишається в історії з незмінними даними. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `DELETE /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; без тіла. `Prefer: code=409, example=SERVICE_PERIOD_ALREADY_STARTED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method DELETE -Path '/cars/car-example/service-unavailabilities/period-example' -Status 409 -Role administrator -Example SERVICE_PERIOD_ALREADY_STARTED
```

### NEG-083. Видалення історичного службового періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-22; REQ-F-076, REQ-F-081 |
| Роль і незалежні передумови | Адміністратор. Час 2026-11-22T09:00:00+02:00 після завершення. |
| Негативний запит до майбутньої системи | `DELETE /api/v1/cars/car-example/service-unavailabilities/period-example`. Без тіла. |
| Очікуваний статус / code / заголовки | 409; error.code=`SERVICE_PERIOD_ALREADY_STARTED`; Content-Type: application/json |
| Перевірки системи | details={}; період лишається в історії з незмінними даними. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `DELETE /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; без тіла. `Prefer: code=409, example=SERVICE_PERIOD_ALREADY_STARTED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method DELETE -Path '/cars/car-example/service-unavailabilities/period-example' -Status 409 -Role administrator -Example SERVICE_PERIOD_ALREADY_STARTED
```

### NEG-084. Створення службового періоду без причини

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-20; REQ-F-074 |
| Роль і незалежні передумови | Адміністратор. Майбутній безконфліктний період; порушено лише reason. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars/car-example/service-unavailabilities`. JSON: `{"startsAt":"2026-11-20T09","endsAt":"2026-11-21T09"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає reason без введеного значення; періоду немає. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars/car-example/service-unavailabilities`; role=administrator; request example=`ServicePeriodCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars/car-example/service-unavailabilities' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample ServicePeriodCreateRequest
```

### NEG-085. Створення службового періоду з пробільною причиною

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-20; REQ-F-074 |
| Роль і незалежні передумови | Адміністратор. Майбутній безконфліктний період; порушено лише reason. |
| Негативний запит до майбутньої системи | `POST /api/v1/cars/car-example/service-unavailabilities`. JSON: `{"startsAt":"2026-11-20T09","endsAt":"2026-11-21T09","reason":" \t "}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає reason без введеного значення; періоду немає. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `POST /api/v1/cars/car-example/service-unavailabilities`; role=administrator; request example=`ServicePeriodCreateRequest`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method POST -Path '/cars/car-example/service-unavailabilities' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample ServicePeriodCreateRequest
```

### NEG-086. Новий початок PATCH службового періоду в минулому

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-21; REQ-F-074, REQ-F-075 |
| Роль і незалежні передумови | Адміністратор. Чинний період ще майбутній; новий початок 2026-11-09T09 у минулому відносно 2026-11-10T12; інших записів для авто немає. Це погоджене проєктне правило підсумкового періоду. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`. JSON: `{"startsAt":"2026-11-09T09"}`. |
| Очікуваний статус / code / заголовки | 422; error.code=`VALIDATION_ERROR`; Content-Type: application/json |
| Перевірки системи | fields позначає startsAt; чинний майбутній період не змінено; REQ-F-073 про створення не приписується PATCH як пряма вимога. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; request example=`ServicePeriodPatch`. `Prefer: code=422, example=VALIDATION_ERROR`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method PATCH -Path '/cars/car-example/service-unavailabilities/period-example' -Status 422 -Role administrator -Example VALIDATION_ERROR -RequestExample ServicePeriodPatch
```

## Неіснуючі ресурси та непідтримувані методи

### NEG-087. Неіснуючий автомобіль у каталозі

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-02; REQ-F-001, REQ-F-002 |
| Роль і незалежні передумови | Гість. car-missing відсутній; публічний маршрут. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-missing`. Без тіла. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | Фіксоване тіло 404; немає ознак внутрішнього пошуку чи діагностики БД. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example`; role=guest; без тіла. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example' -Status 404 -Role guest -Example NOT_FOUND
```

### NEG-088. Приховане авто недоступне клієнту як ресурс каталогу

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-02; REQ-F-068 |
| Роль і незалежні передумови | Клієнт. car-example існує, але hidden=true; це не перевірка availability. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example`. Без тіла. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | Той самий NOT_FOUND, що для відсутнього авто; приховані характеристики не надаються. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example`; role=guest; без тіла. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example' -Status 404 -Role guest -Example NOT_FOUND
```

### NEG-089. Доступність неіснуючого авто

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-03; REQ-F-006 |
| Роль і незалежні передумови | Гість. car-missing відсутній, обидві межі коректні. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-missing/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`. Без тіла. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | 404, а не available=false для неіснуючого ресурсу; для відомого прихованого авто контракт натомість задає 200/false. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`; role=guest; без тіла. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 404 -Role guest -Example NOT_FOUND
```

### NEG-090. Неіснуюче бронювання для автентифікованого клієнта

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-12; REQ-F-084, REQ-F-089 |
| Роль і незалежні передумови | Клієнт. Сесія К чинна; booking-missing не існує. |
| Негативний запит до майбутньої системи | `GET /api/v1/bookings/booking-missing`. Без тіла. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | Повністю те саме тіло, що в сценарії чужого бронювання: NOT_FOUND, «Ресурс не знайдено.», details={}. Це порівняння очікувань двох незалежних фікстур, не послідовність mock. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/bookings/booking-example`; role=client; без тіла. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/bookings/booking-example' -Status 404 -Role client -Example NOT_FOUND
```

### NEG-091. Перелік службових періодів неіснуючого авто

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-18; REQ-F-087, REQ-F-089 |
| Роль і незалежні передумови | Адміністратор. Роль дозволена; car-missing відсутній. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-missing/service-unavailabilities`. Без тіла. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | details={}; жодних службових причин або деталей сховища. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/service-unavailabilities`; role=administrator; без тіла. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/service-unavailabilities' -Status 404 -Role administrator -Example NOT_FOUND
```

### NEG-092. periodId належить іншому автомобілю

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-19; REQ-F-087, REQ-F-089 |
| Роль і незалежні передумови | Адміністратор. Обидва ресурси існують, але period-other належить не car-example. Роль дозволена; порушено лише зв’язок, визначений контрактом. |
| Негативний запит до майбутньої системи | `GET /api/v1/cars/car-example/service-unavailabilities/period-other`. Без тіла. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | Фіксований NOT_FOUND без розкриття фактичного carId чи reason. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example/service-unavailabilities/period-example`; role=administrator; без тіла. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example/service-unavailabilities/period-example' -Status 404 -Role administrator -Example NOT_FOUND
```

### NEG-093. Невідомий маршрут

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-02 лише як контекст носія; негативний маршрут не має OP; Прямого REQ немає; технічна маршрутизація за error-model.md |
| Роль і незалежні передумови | Гість. Немає жодної операції для /unknown-resource. OP-02 тут лише контекст статичного носія, а не OP нового маршруту; прямого функціонального REQ немає, правило задано error-model.md. |
| Негативний запит до майбутньої системи | `GET /api/v1/unknown-resource`. Без тіла. |
| Очікуваний статус / code / заголовки | 404; error.code=`NOT_FOUND`; Content-Type: application/json |
| Перевірки системи | Фіксоване тіло NOT_FOUND; маршруту чи нового OP не створюємо. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/cars/car-example`; role=guest; без тіла. `Prefer: code=404, example=NOT_FOUND`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/cars/car-example' -Status 404 -Role guest -Example NOT_FOUND
```

### NEG-094. Заборонена зміна створеного бронювання через PATCH

| Поле | Підготовлений сценарій |
| --- | --- |
| OP / REQ | OP-12; REQ-F-045 |
| Роль і незалежні передумови | Клієнт. Власне бронювання існує; для /bookings/{bookingId} описаний лише GET, PATCH не підтримується. |
| Негативний запит до майбутньої системи | `PATCH /api/v1/bookings/booking-example`. JSON: `{"startsAt":"2026-11-13T09"}`. |
| Очікуваний статус / code / заголовки | 405; error.code=`METHOD_NOT_ALLOWED`; Content-Type: application/json; Allow: GET для /bookings/{bookingId} |
| Перевірки системи | Allow містить GET (порядок методів не тестується); details={}; авто й період бронювання не змінюються. Статичний носій — GET цього URI з Prefer: code=405. Спільні перевірки ErrorResponse і приватності — у вступі. |
| Статичне відтворення Prism | Валідний носій: `GET /api/v1/bookings/booking-example`; role=client; без тіла. `Prefer: code=405, example=METHOD_NOT_ALLOWED`. Це лише показ прикладу, не виконання негативного запиту. |

```powershell
Invoke-NegativeMock -Method GET -Path '/bookings/booking-example' -Status 405 -Role client -Example METHOD_NOT_ALLOWED
```

## Повнота, приклади та прогалини

Підготовлено **94 незалежні негативні сценарії**, які посилаються на **22 операції** та всі вісім запитаних напрямів. Для невідомого маршруту OP не вигадується; для 405 указано контекст відомого URI й окремий дозволений mock-носій. Негативні виклики недопустимого методу не створюють нових операцій.

Усі потрібні response examples уже є в OpenAPI; специфікацію, коди й бізнес-правила не змінено, нових examples не додано. Валідація/статична перевірка посилань не є виконанням HTTP-сценаріїв. 500/503 описані моделлю помилок, але ін’єкція інфраструктурних аварій не входить до цих восьми напрямів.

| Питання / межа | Зафіксований стан |
| --- | --- |
| Відкриті питання контракту | Строк сесії, вплив зміни пароля на чинні сесії та календарне Q-07 не вирішено. Для відмови автентифікації не задаємо нового строку токена; для DST перевіряємо введені межі, не проміжні календарні обчислення |
| Кілька незалежних порушень | Загальний пріоритет усіх помилок не визначений. Фікстури ізолюють порушення; відомі правила 401/403 до існування ресурсу та розмежування активного стану/клієнтського дедлайну збережено |
| Конкретизація details.fields | Модель дозволяє шлях поля або $, але не задає точного каталогу текстів і локалізації всіх міжпольових помилок. Точний field для порядку меж не вигадується. Для named example використовується наявний загальний $ |
| Розбіжність інструмента й контракту | Власні 404/405/422 Prism та gateway можуть мати іншу модель. Наявність 405 в responses не створює реального PATCH-маршруту. Для показу ErrorResponse використано дозволені mock-носії; реальні негативні запити перевірятимуться на реалізації |
| Публічна перевірка недоступного авто | Для існуючого прихованого/зайнятого авто OP-03 повертає 200 з available=false, OP-01 — відфільтрований список; це не негативні 409 CAR_UNAVAILABLE. 409 застосовано лише до OP-09/OP-10 |

Нових прогалин, що потребують нового маршруту, коду або бізнес-правила для цих сценаріїв, не виявлено; перелічені невирішені деталі та обмеження mock не закриваються припущеннями.

DST-фікстури 2026-03-29T03 і 2026-10-25T03 звірено офлайн з Europe/Kyiv у встановленому tzdata 2026.6: відповідно 0 та 2 входження UTC. Це підготовка часових даних, не запуск API й не розв’язання Q-07; при зміні правил часової зони фікстури слід повторно звірити.

**HTTP-сценарії не запускалися; результатів NEG PASS/FAIL немає.** Виконання та фіксація результатів — наступний етап. API-GATE не виконано; коміту та push немає.
