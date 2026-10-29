# Позитивні сценарії REST API

**Статус: підготовлено, не виконано.** Джерела: [операції](operations.md), [трасованість](traceability.md), [схеми](data-schemas.md), [модель помилок](error-model.md), [OpenAPI](openapi.yaml), [AC](../spec/acceptance-criteria.md) та [BDD](../spec/bdd-scenarios.md). Це позитивні частини критеріїв і BDD, а не заявка на повне покриття всіх 92 вимог або негативних гілок.

Кожен POS незалежний. Для **майбутньої перевірки системи за SRS** потрібні власні ізольовані фікстури й керований серверний час. Якщо не зазначено інше, контрольований час — 2026-11-10T12:00:00+02:00 у Europe/Kyiv; дати прикладів не прив’язані до часу виконання документа. Приклади з іншим станом того самого id — альтернативні фікстури, не кроки одного ланцюжка.

Для **статичного mock** ролі client/administrator задають лише демонстраційний Bearer, а проєкцію/стан/успіх визначає Prefer. Mock не обчислює календарні межі/вартість, не перевіряє справжні ролі чи власність, не зберігає запити й не виконує переходи станів. Не треба реєструватися або отримувати токен іншим POS: усі вхідні дані вже підготовлені в окремих examples. Навіть однакові id чи priceConfirmationToken не створюють залежності запитів.

## Команди для майбутнього відтворення

Підготовлені команди виконуються від кореня репозиторію після запуску за [mock-guide.md](mock-guide.md). **Зараз їх не запускали.** Функцію нижче достатньо визначити один раз у Windows PowerShell; це клієнт запитів, без серверних обробників. Вона читає тіло з наявного components/examples, не з результату попереднього HTTP-запиту. JSON використовує ASCII-escape для відтворюваного передавання українських рядків у PowerShell 5.1.

```powershell
function Invoke-PositiveMock {
    param(
        [string]$Method,
        [string]$Path,
        [int]$Status,
        [ValidateSet('guest', 'client', 'administrator')][string]$Role = 'guest',
        [string]$Example,
        [string]$RequestExample
    )
    $mockHeaders = @{ Accept = 'application/json'; Prefer = "code=$Status" }
    if ($Example) { $mockHeaders.Prefer += ", example=$Example" }
    if ($Role -ne 'guest') { $mockHeaders.Authorization = "Bearer mock-$Role" }
    $mockArguments = @{
        UseBasicParsing = $true
        Method = $Method
        Uri = 'http://127.0.0.1:4010/api/v1' + $Path
        Headers = $mockHeaders
    }
    if ($RequestExample) {
        $mockBody = & '.\.venv-api-validation\Scripts\python.exe' -c "import json,sys,yaml; from pathlib import Path; s=yaml.safe_load(Path('api/openapi.yaml').read_text(encoding='utf-8')); print(json.dumps(s['components']['examples'][sys.argv[1]]['value'], ensure_ascii=True))" $RequestExample
        if ($LASTEXITCODE -ne 0) { throw 'Cannot load the OpenAPI request example.' }
        $mockArguments.ContentType = 'application/json'
        $mockArguments.Body = [System.Text.Encoding]::UTF8.GetBytes(($mockBody -join "`n"))
    }
    $mockResponse = Invoke-WebRequest @mockArguments
    [pscustomobject]@{
        Status = $mockResponse.StatusCode
        Headers = $mockResponse.Headers
        Content = $mockResponse.Content
    }
}
```

У кожній картці «Очікування SRS» описує реальну систему. Для майбутнього mock-відтворення перевіряються лише вибраний статус, форма/поля статичного тіла та, за наявності, точний збіг з example. Інваріанти зберігання, порядок зміни станів, реальність Location та прив’язка токена до користувача не доводяться. Відповіді з тілом мають бути application/json за схемою відповідної операції; 204 — без тіла, тому named response example не застосовується, лише Prefer: code=204.

Посилання на REQ у картці означає обґрунтування її призначення/передумов/очікувань, а не доказ виконання всіх гілок цієї вимоги. Для повної операційної трасованості див. traceability.md. Для А діють однакові повноваження та серверні перевірки прямого API (REQ-F-087–REQ-F-089); для К — власні дані. Негативні перевірки цих заборон тут не виконуються.

## Каталог і доступність

### POS-001. Каталог гостя без періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-01; REQ-F-001, REQ-F-002, REQ-F-003 |
| Основа AC/BDD | AC-F-001-01–AC-F-003-01; BDD-001 |
| Передумови SRS | Гість; у незалежній фікстурі є неприховане car-example і приховане інше авто; період не вибрано. |
| Роль / mock-заголовок | Без Bearer (гість або публічний вхід) |
| Запит | `GET /api/v1/cars`. Без тіла. |
| Очікування SRS | 200; схема PublicCarList; характеристики й тариф, тільки неприховані авто; немає available, hidden чи futureBookingsCount. |
| Статичне відтворення | Response example: `PublicCarList`; `Prefer: code=200, example=PublicCarList`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars' -Status 200 -Role guest -Example PublicCarList
```

### POS-002. Каталог клієнта без періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-01; REQ-F-001, REQ-F-002, REQ-F-003 |
| Основа AC/BDD | AC-F-001-01–AC-F-003-01; BDD-001 |
| Передумови SRS | К увійшов; каталог доступний і після входу, період не вибрано. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/cars`. Без тіла. |
| Очікування SRS | 200; публічна проєкція навіть після входу К; жодного твердження про доступність. |
| Статичне відтворення | Response example: `PublicCarList`; `Prefer: code=200, example=PublicCarList`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars' -Status 200 -Role client -Example PublicCarList
```

### POS-003. Адміністративна проєкція публічного каталогу

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-01; REQ-F-003, REQ-F-069, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-003-01, AC-F-069-01, AC-F-087-01–AC-F-089-01; проєктна деталізація |
| Передумови SRS | А увійшов; car-example неприховане, має одне майбутнє підтверджене бронювання. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/cars`. Без тіла. |
| Очікування SRS | 200; AdminCarList, hidden=false, futureBookingsCount=1; приховані авто все одно не входять у публічний каталог. |
| Статичне відтворення | Response example: `AdminCarList`; `Prefer: code=200, example=AdminCarList`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars' -Status 200 -Role administrator -Example AdminCarList
```

### POS-004. Пошук гостем із суміжним бронюванням

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-01; REQ-F-004, REQ-F-005, REQ-F-007, REQ-F-008 |
| Основа AC/BDD | AC-F-004-01, AC-F-005-01, AC-F-008-01; BDD-002 (успішна гілка) |
| Передумови SRS | Гість; car-example неприховане; наявна оренда завершується рівно 2026-11-12T09, решта періоду вільна. Інші конфліктні авто вилучаються з результату системою. |
| Роль / mock-заголовок | Без Bearer (гість або публічний вхід) |
| Запит | `GET /api/v1/cars?startsAt=2026-11-12T09&endsAt=2026-11-14T09`. Без тіла. |
| Очікування SRS | 200; схема PublicCarList; car-example входить у результат як доступне на весь період; суміжність не є перетином. |
| Статичне відтворення | Response example: `PublicCarList`; `Prefer: code=200, example=PublicCarList`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 200 -Role guest -Example PublicCarList
```

### POS-005. Пошук адміністратором у публічному каталозі

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-01; REQ-F-004, REQ-F-005, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-004-01–AC-F-005-01; проєктна рольова проєкція |
| Передумови SRS | А; car-example доступне на заданий період; приховані авто не включаються. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/cars?startsAt=2026-11-12T09&endsAt=2026-11-14T09`. Без тіла. |
| Очікування SRS | 200; AdminCarList для відібраних доступних авто; hidden=false; адміністративний лічильник не є ознакою зайнятості саме цього періоду. |
| Статичне відтворення | Response example: `AdminCarList`; `Prefer: code=200, example=AdminCarList`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 200 -Role administrator -Example AdminCarList
```

### POS-006. Клієнт читає характеристики автомобіля

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-02; REQ-F-001, REQ-F-002 |
| Основа AC/BDD | AC-F-001-01, AC-F-002-01 |
| Передумови SRS | К; неприховане car-example існує. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/cars/car-example`. Без тіла. |
| Очікування SRS | 200; PublicCar: id, characteristics, dailyRate="1500.00", currency=UAH; без адміністративних полів. |
| Статичне відтворення | Response example: `PublicCar`; `Prefer: code=200, example=PublicCar`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars/car-example' -Status 200 -Role client -Example PublicCar
```

### POS-007. Адміністратор читає приховане авто

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-02; REQ-F-068, REQ-F-069, REQ-F-071, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-068-01, AC-F-069-01, AC-F-071-01; допоміжне читання |
| Передумови SRS | А; car-example вже приховане в цій окремій фікстурі, має майбутнє бронювання; не результат іншого POS. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/cars/car-example`. Без тіла. |
| Очікування SRS | 200; AdminCar, hidden=true, futureBookingsCount=1; дані для майбутнього повернення авто. |
| Статичне відтворення | Response example: `AdminCarHidden`; `Prefer: code=200, example=AdminCarHidden`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars/car-example' -Status 200 -Role administrator -Example AdminCarHidden
```

### POS-008. Гість перевіряє доступне авто

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-03; REQ-F-006, REQ-F-007, REQ-F-008, REQ-F-092 |
| Основа AC/BDD | AC-F-006-01, AC-F-008-01, AC-F-092-01; BDD-002 |
| Передумови SRS | Неприховане car-example; попередня оренда завершується рівно на початку запиту; інших перетинів немає. Вхід не потрібен. |
| Роль / mock-заголовок | Без Bearer (гість або публічний вхід) |
| Запит | `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`. Без тіла. |
| Очікування SRS | 200; AvailabilityResponse, available=true, точні carId/межі/timezone; без причин чи чужих даних. |
| Статичне відтворення | Response example: `AvailabilityTrue`; `Prefer: code=200, example=AvailabilityTrue`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 200 -Role guest -Example AvailabilityTrue
```

### POS-009. Клієнт перевіряє доступне авто

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-03; REQ-F-006, REQ-F-007, REQ-F-008, REQ-F-092 |
| Основа AC/BDD | AC-F-006-01, AC-F-008-01, AC-F-092-01; BDD-002 |
| Передумови SRS | Неприховане car-example; попередня оренда завершується рівно на початку запиту; інших перетинів немає. Відповідна роль увійшла. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`. Без тіла. |
| Очікування SRS | 200; AvailabilityResponse, available=true, точні carId/межі/timezone; без причин чи чужих даних. |
| Статичне відтворення | Response example: `AvailabilityTrue`; `Prefer: code=200, example=AvailabilityTrue`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 200 -Role client -Example AvailabilityTrue
```

### POS-010. Адміністратор перевіряє доступне авто

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-03; REQ-F-006, REQ-F-007, REQ-F-008, REQ-F-092 |
| Основа AC/BDD | AC-F-006-01, AC-F-008-01, AC-F-092-01; BDD-002 |
| Передумови SRS | Неприховане car-example; попередня оренда завершується рівно на початку запиту; інших перетинів немає. Відповідна роль увійшла. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09`. Без тіла. |
| Очікування SRS | 200; AvailabilityResponse, available=true, точні carId/межі/timezone; без причин чи чужих даних. |
| Статичне відтворення | Response example: `AvailabilityTrue`; `Prefer: code=200, example=AvailabilityTrue`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars/car-example/availability?startsAt=2026-11-12T09&endsAt=2026-11-14T09' -Status 200 -Role administrator -Example AvailabilityTrue
```

## Реєстрація, автентифікація й профіль

### POS-011. Публічна реєстрація клієнта

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-04; REQ-F-009, REQ-F-010, REQ-F-014, REQ-F-082 |
| Основа AC/BDD | AC-F-009-01, AC-F-010-01, AC-F-014-01, AC-F-082-01; BDD-003 (створення) |
| Передумови SRS | Гість; email вільний; усі реєстраційні дані допустимі. |
| Роль / mock-заголовок | Без Bearer (гість або публічний вхід) |
| Запит | `POST /api/v1/clients`. `{"firstName":"Олена","lastName":"Коваль","email":"client@example.com","phone":"+380501234567","password":"ExamplePass8 "}`; request example: `RegistrationRequest`. |
| Очікування SRS | 201; RegistrationResponse з profile і role=client; немає Location, accessToken чи пароля; автоматичного входу немає. |
| Статичне відтворення | Response example: `RegistrationResponse`; `Prefer: code=201, example=RegistrationResponse`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/clients' -Status 201 -Role guest -Example RegistrationResponse -RequestExample RegistrationRequest
```

### POS-012. Успішний вхід клієнта

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-05; REQ-F-010, REQ-F-012, REQ-F-013, REQ-F-019 |
| Основа AC/BDD | AC-F-010-01, AC-F-012-01, AC-F-013-01, AC-F-019-01; BDD-004 (успішний вхід) |
| Передумови SRS | Існуючий клієнт, пароль відповідає запису, блокування немає; можливі попередні невдалі спроби до межі блокування. Обліковий запис не створюється іншим POS. |
| Роль / mock-заголовок | Без Bearer (гість або публічний вхід) |
| Запит | `POST /api/v1/sessions`. `{"email":"client@example.com","password":"ExamplePass8 "}`; request example: `LoginRequest`. |
| Очікування SRS | 201; LoginResponse, непорожній accessToken, tokenType=Bearer, role=client; система скидає лічильник помилок, mock цього не доводить. |
| Статичне відтворення | Response example: `LoginClient`; `Prefer: code=201, example=LoginClient`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/sessions' -Status 201 -Role guest -Example LoginClient -RequestExample LoginRequest
```

### POS-013. Успішний вхід адміністратора

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-05; REQ-F-010, REQ-F-012, REQ-F-013, REQ-F-019, REQ-F-020 |
| Основа AC/BDD | AC-F-012-01, AC-F-013-01, AC-F-019-01, AC-F-020-01; BDD-004 (вхід після спливу блокування) |
| Передумови SRS | Адміністратора створено поза публічним API; блокування вже завершилося, пароль правильний. До входу запит публічний. |
| Роль / mock-заголовок | Без Bearer (гість або публічний вхід) |
| Запит | `POST /api/v1/sessions`. `{"email":"admin@example.com","password":"ExamplePass8 "}`; request example: `LoginAdminRequest`. |
| Очікування SRS | 201; LoginResponse, role=administrator, accountId=admin-example; tokenType=Bearer; строк токена не перевіряється як невирішений. |
| Статичне відтворення | Response example: `LoginAdmin`; `Prefer: code=201, example=LoginAdmin`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/sessions' -Status 201 -Role guest -Example LoginAdmin -RequestExample LoginAdminRequest
```

### POS-014. Перегляд власного профілю

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-06; REQ-F-021, REQ-F-089 |
| Основа AC/BDD | AC-F-021-01; BDD-005 (читання профілю) |
| Передумови SRS | К увійшов; незалежна фікстура профілю містить телефон +380501234567. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/profile`. Без тіла. |
| Очікування SRS | 200; Profile власника, усі п’ять полів, без паролів/хешів. |
| Статичне відтворення | Response example: `Profile`; `Prefer: code=200, example=Profile`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/profile' -Status 200 -Role client -Example Profile
```

### POS-015. Зміна власного телефону

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-07; REQ-F-021, REQ-F-024, REQ-F-025, REQ-F-086, REQ-F-089 |
| Основа AC/BDD | AC-F-021-01, AC-F-024-01, AC-F-025-01; BDD-005 (оновлення) |
| Передумови SRS | К; профіль і раніше створене бронювання підготовлено окремо; зміна дозволеного телефону. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `PATCH /api/v1/profile`. `{"phone":"+380671234567"}`; request example: `ProfilePatch`. |
| Очікування SRS | 200; Profile.phone=+380671234567, email незмінний. За SRS актуальні контакти доступні в бронюваннях, їх авто/період/суми не змінено; це не перевіряється наступним статичним GET. |
| Статичне відтворення | Response example: `ProfileUpdated`; `Prefer: code=200, example=ProfileUpdated`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method PATCH -Path '/profile' -Status 200 -Role client -Example ProfileUpdated -RequestExample ProfilePatch
```

### POS-016. Зміна власного пароля

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-08; REQ-F-014, REQ-F-022, REQ-F-086, REQ-F-089 |
| Основа AC/BDD | AC-F-014-01, AC-F-022-01 |
| Передумови SRS | К; currentPassword правильний, newPassword має від 8 символів. Пробіли в обох паролях зберігаються. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `PUT /api/v1/profile/password`. `{"currentPassword":"ExamplePass8 ","newPassword":"NewExamplePass9 "}`; request example: `PasswordChangeRequest`. |
| Очікування SRS | 204, порожнє тіло. За SRS новий пароль встановлюється; mock не зберігає його й не підтверджує подальший вхід. Наслідки для сесій не визначаються. |
| Статичне відтворення | Без response example (204); `Prefer: code=204`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method PUT -Path '/profile/password' -Status 204 -Role client -RequestExample PasswordChangeRequest
```

## Вартість і створення бронювання

### POS-017. Попередній розрахунок вартості

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-09; REQ-F-027, REQ-F-028, REQ-F-031, REQ-F-032, REQ-F-033, REQ-F-034, REQ-F-035, REQ-F-036, REQ-F-037, REQ-F-038 |
| Основа AC/BDD | AC-F-027-01, AC-F-028-01, AC-F-035-01–AC-F-038-01; BDD-006 (показ вартості) |
| Передумови SRS | К; картина доступності та тариф 1500.00 підготовлені; період у майбутньому, 2 календарні доби, у межах 90 днів. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `POST /api/v1/booking-quotes`. `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09"}`; request example: `QuoteRequest`. |
| Очікування SRS | 200; Quote, billableDays=2, totalPrice="3000.00", UAH і непорожній priceConfirmationToken; система не резервує авто. |
| Статичне відтворення | Response example: `Quote`; `Prefer: code=200, example=Quote`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/booking-quotes' -Status 200 -Role client -Example Quote -RequestExample QuoteRequest
```

### POS-018. Створення бронювання за актуальною ціною із суміжністю

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-10; REQ-F-008, REQ-F-026, REQ-F-027, REQ-F-028, REQ-F-031, REQ-F-032, REQ-F-033, REQ-F-034, REQ-F-035, REQ-F-036, REQ-F-037, REQ-F-040, REQ-F-043, REQ-F-044, REQ-F-045, REQ-F-051 |
| Основа AC/BDD | AC-F-008-01, AC-F-026-01, AC-F-040-01, AC-F-043-01; BDD-006; BDD-007 (допустимий період) |
| Передумови SRS | К; незалежна фікстура вже містить чинний токен для цього клієнта/авто/періоду, підтверджену показану ціну, тариф незмінний; попереднє бронювання завершується рівно 2026-11-12T09. Не залежить від POS розрахунку. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `POST /api/v1/bookings`. `{"carId":"car-example","startsAt":"2026-11-12T09","endsAt":"2026-11-14T09","priceConfirmationToken":"price-confirmation-example"}`; request example: `BookingCreateRequest`. |
| Очікування SRS | 201; ClientBooking, status=confirmed, cancellation=null, точні car/межі, зафіксовані 1500.00 і 3000.00, billableDays=2, межа 2026-11-11T09:00:00+02:00; у системі коректний Location та атомарне резервування. |
| Статичне відтворення | Response example: `ClientBooking`; `Prefer: code=201, example=ClientBooking`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/bookings' -Status 201 -Role client -Example ClientBooking -RequestExample BookingCreateRequest
```

## Перегляд бронювань та станів

### POS-019. Клієнт читає власний список

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-11; REQ-F-043, REQ-F-044, REQ-F-046, REQ-F-084, REQ-F-089 |
| Основа AC/BDD | AC-F-043-01, AC-F-044-01, AC-F-046-01 |
| Передумови SRS | К; власне підтверджене бронювання підготовлено фікстурою; поточний тариф авто може відрізнятися від зафіксованого. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/bookings`. Без тіла. |
| Очікування SRS | 200; ClientBookingList; тільки власні записи, фіксовані тариф/сума; немає client або authorAccountId. |
| Статичне відтворення | Response example: `ClientBookingList`; `Prefer: code=200, example=ClientBookingList`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/bookings' -Status 200 -Role client -Example ClientBookingList
```

### POS-020. Адміністратор читає всі бронювання

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-11; REQ-F-024, REQ-F-047, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-024-01, AC-F-047-01; BDD-005 (актуальні контакти) |
| Передумови SRS | А; записи та актуальні контакти клієнта підготовлені до сценарію, без попереднього PATCH у mock. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/bookings`. Без тіла. |
| Очікування SRS | 200; AdminBookingList; client містить актуальні firstName, lastName, email, phone. Приклад має один запис і не доводить повноту реального списку. |
| Статичне відтворення | Response example: `AdminBookingList`; `Prefer: code=200, example=AdminBookingList`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/bookings' -Status 200 -Role administrator -Example AdminBookingList
```

### POS-021. Клієнт читає підтверджене бронювання

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-12; REQ-F-043, REQ-F-046, REQ-F-048, REQ-F-050, REQ-F-051, REQ-F-084 |
| Основа AC/BDD | AC-F-043-01, AC-F-046-01, AC-F-048-01; BDD-006 |
| Передумови SRS | К; власний booking-example існує, оренда ще не почалася. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/bookings/booking-example`. Без тіла. |
| Очікування SRS | 200; ClientBooking, status=confirmed, cancellation=null, незмінні параметри й ціна; межа скасування присутня. |
| Статичне відтворення | Response example: `ClientBooking`; `Prefer: code=200, example=ClientBooking`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/bookings/booking-example' -Status 200 -Role client -Example ClientBooking
```

### POS-022. Адміністратор читає конкретне бронювання

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-12; REQ-F-024, REQ-F-047, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-024-01, AC-F-047-01; BDD-005 |
| Передумови SRS | А; booking-example і актуальний профіль його клієнта існують як незалежна фікстура. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/bookings/booking-example`. Без тіла. |
| Очікування SRS | 200; AdminBooking зі вкладеним client; dailyRate/totalPrice бронювання не підміняються поточними даними авто. |
| Статичне відтворення | Response example: `AdminBooking`; `Prefer: code=200, example=AdminBooking`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/bookings/booking-example' -Status 200 -Role administrator -Example AdminBooking
```

### POS-023. Клієнт читає історію адміністративного скасування

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-12; REQ-F-046, REQ-F-060, REQ-F-062, REQ-F-063, REQ-F-091 |
| Основа AC/BDD | AC-F-060-01, AC-F-062-01, AC-F-063-01, AC-F-091-01; BDD-012 (видимість) |
| Передумови SRS | К; власний booking-example вже скасований адміністратором у фікстурі; не результат попереднього запиту mock. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/bookings/booking-example`. Без тіла. |
| Очікування SRS | 200; status=cancelled; cancellation має час, authorRole=administrator і причину; немає authorAccountId чи особистих даних адміністратора. |
| Статичне відтворення | Response example: `ClientBookingCancelled`; `Prefer: code=200, example=ClientBookingCancelled`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/bookings/booking-example' -Status 200 -Role client -Example ClientBookingCancelled
```

### POS-024. Адміністратор читає автора скасування

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-12; REQ-F-047, REQ-F-060, REQ-F-062, REQ-F-064, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-062-01, AC-F-064-01; BDD-012 (автор) |
| Передумови SRS | А; скасований booking-example уже існує в окремій фікстурі. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/bookings/booking-example`. Без тіла. |
| Очікування SRS | 200; AdminBooking, cancellation.authorAccountId=admin-example, причина й час присутні; client має актуальні контакти. |
| Статичне відтворення | Response example: `AdminBookingCancelled`; `Prefer: code=200, example=AdminBookingCancelled`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/bookings/booking-example' -Status 200 -Role administrator -Example AdminBookingCancelled
```

### POS-025. Читання активного стану на початку

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-12; REQ-F-046, REQ-F-048, REQ-F-050 |
| Основа AC/BDD | AC-F-048-01, AC-F-050-01; BDD-013 (лише позитивне читання стану) |
| Передумови SRS | К; власне нескасоване бронювання; контрольований серверний час рівно 2026-11-12T09:00:00+02:00. Жодних дій фізичної видачі. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/bookings/booking-example`. Без тіла. |
| Очікування SRS | 200; status=active, cancellation=null, ціна/період збережені. Mock повертає заздалегідь вибраний active без власного переходу часу. |
| Статичне відтворення | Response example: `ClientBookingActive`; `Prefer: code=200, example=ClientBookingActive`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/bookings/booking-example' -Status 200 -Role client -Example ClientBookingActive
```

### POS-026. Читання завершеного стану на завершенні

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-12; REQ-F-046, REQ-F-049, REQ-F-050 |
| Основа AC/BDD | AC-F-049-01, AC-F-050-01; BDD-013 (лише позитивне читання стану) |
| Передумови SRS | К; власне нескасоване бронювання; контрольований час рівно 2026-11-14T09:00:00+02:00, без підтвердження фізичного повернення. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `GET /api/v1/bookings/booking-example`. Без тіла. |
| Очікування SRS | 200; status=completed, cancellation=null, параметри збережені. Mock не доводить автоматичного завершення. |
| Статичне відтворення | Response example: `ClientBookingCompleted`; `Prefer: code=200, example=ClientBookingCompleted`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/bookings/booking-example' -Status 200 -Role client -Example ClientBookingCompleted
```

## Скасування бронювання

### POS-027. Клієнт скасовує до межі без тіла

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-13; REQ-F-051, REQ-F-054, REQ-F-056, REQ-F-060, REQ-F-061, REQ-F-062, REQ-F-085 |
| Основа AC/BDD | AC-F-054-01, AC-F-056-01, AC-F-060-01–AC-F-062-01; BDD-011 (до межі) |
| Передумови SRS | К; власне підтверджене booking-example; контрольований час 2026-11-10T12:00:00+02:00, до межі та початку. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `POST /api/v1/bookings/booking-example/cancellation`. Без тіла. |
| Очікування SRS | 201; ClientCancellation, authorRole=client, reason=null, cancelledAt відповідає фікстурі, без authorAccountId. За SRS стан cancelled, період одразу вільний, історія збережена; mock цього не виконує. |
| Статичне відтворення | Response example: `ClientCancellation`; `Prefer: code=201, example=ClientCancellation`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 201 -Role client -Example ClientCancellation
```

### POS-028. Клієнт скасовує рівно на дозволеній межі

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-13; REQ-F-051, REQ-F-054, REQ-F-056, REQ-F-060, REQ-F-061, REQ-F-062 |
| Основа AC/BDD | AC-F-051-01, AC-F-054-01, AC-F-056-01; BDD-011 (рівно на межі) |
| Передумови SRS | К; власне confirmed з початком 2026-11-12T09; серверний час зафіксовано рівно 2026-11-11T09:00:00+02:00, що дорівнює clientCancellationDeadline. Оренда ще не почалася. |
| Роль / mock-заголовок | Клієнт; Authorization: Bearer mock-client |
| Запит | `POST /api/v1/bookings/booking-example/cancellation`. `{}`; request example: `ClientCancellationRequest`. |
| Очікування SRS | 201; reason=null, authorRole=client, cancelledAt=2026-11-11T09:00:00+02:00. Дозволеність включної межі та звільнення періоду — очікування SRS, не властивість mock. |
| Статичне відтворення | Response example: `ClientCancellationAtDeadline`; `Prefer: code=201, example=ClientCancellationAtDeadline`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 201 -Role client -Example ClientCancellationAtDeadline -RequestExample ClientCancellationRequest
```

### POS-029. Адміністратор скасовує після клієнтської межі

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-13; REQ-F-057, REQ-F-058, REQ-F-060, REQ-F-061, REQ-F-062, REQ-F-064, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-057-01, AC-F-058-01, AC-F-060-01–AC-F-062-01, AC-F-064-01; BDD-012 (успішна гілка) |
| Передумови SRS | А; підтверджене бронювання; час 2026-11-11T12:00:00+02:00 після межі К, але строго до початку. Причина містить непробільні символи. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `POST /api/v1/bookings/booking-example/cancellation`. `{"reason":"Заміна автомобіля в автопарку неможлива."}`; request example: `AdminCancellationRequest`. |
| Очікування SRS | 201; AdminCancellation: authorRole=administrator, authorAccountId=admin-example, час і непорожня причина. У системі атомарні cancelled/звільнення/історія; mock лише відтворює приклад. |
| Статичне відтворення | Response example: `AdminCancellation`; `Prefer: code=201, example=AdminCancellation`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/bookings/booking-example/cancellation' -Status 201 -Role administrator -Example AdminCancellation -RequestExample AdminCancellationRequest
```

## Адміністративне керування автомобілями

### POS-030. Перелік автопарку з прихованим авто

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-14; REQ-F-066, REQ-F-068, REQ-F-069, REQ-F-071, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-068-01, AC-F-069-01, AC-F-071-01; допоміжне адміністративне читання |
| Передумови SRS | А; фікстура містить приховане car-example з одним майбутнім confirmed. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/admin/cars`. Без тіла. |
| Очікування SRS | 200; AdminCarList, приховане авто не вилучене зі службового переліку, hidden=true, futureBookingsCount=1. |
| Статичне відтворення | Response example: `AdminCarListWithHidden`; `Prefer: code=200, example=AdminCarListWithHidden`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/admin/cars' -Status 200 -Role administrator -Example AdminCarListWithHidden
```

### POS-031. Додавання автомобіля

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-15; REQ-F-065, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-065-01, AC-F-087-01–AC-F-089-01 |
| Передумови SRS | А; допустимі характеристики й dailyRate>0; новий car-example у цій фікстурі не має бронювань. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `POST /api/v1/cars`. `{"characteristics":{"Марка":"Porsche","Модель":"911"},"dailyRate":"1500.00"}`; request example: `CarCreateRequest`. |
| Очікування SRS | 201; AdminCar, hidden=false типово, futureBookingsCount=0, тариф 1500.00 UAH. Система створює авто та Location; mock не створює запису. |
| Статичне відтворення | Response example: `CreatedCar`; `Prefer: code=201, example=CreatedCar`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/cars' -Status 201 -Role administrator -Example CreatedCar -RequestExample CarCreateRequest
```

### POS-032. Редагування характеристик і тарифу

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-16; REQ-F-044, REQ-F-066, REQ-F-067, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-044-01, AC-F-066-01, AC-F-067-01 |
| Передумови SRS | А; car-example існує; є бронювання із зафіксованими 1500.00/3000.00. Контакт зі станом інших POS не потрібен. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `PATCH /api/v1/cars/car-example`. `{"characteristics":{"Марка":"Porsche","Модель":"911 Carrera"},"dailyRate":"1800.00"}`; request example: `CarDetailsPatch`. |
| Очікування SRS | 200; CarPatchResponse: Модель="911 Carrera", dailyRate="1800.00", warnings=[]; characteristics замінено повністю. За SRS старі ціни бронювання незмінні; mock повертає тільки приклад авто. |
| Статичне відтворення | Response example: `CarDetailsUpdated`; `Prefer: code=200, example=CarDetailsUpdated`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method PATCH -Path '/cars/car-example' -Status 200 -Role administrator -Example CarDetailsUpdated -RequestExample CarDetailsPatch
```

### POS-033. Приховування з попередженням

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-16; REQ-F-068, REQ-F-069, REQ-F-070, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-068-01–AC-F-070-01; BDD-014 (приховування) |
| Передумови SRS | А; неприховане car-example має одне майбутнє підтверджене бронювання й окремий службовий період. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `PATCH /api/v1/cars/car-example`. `{"hidden":true}`; request example: `CarPatch`. |
| Очікування SRS | 200; car.hidden=true; FUTURE_BOOKINGS_EXIST і futureBookingsCount=1, збігається з car.futureBookingsCount. За SRS бронювання не скасовано; попередження не блокує дію. |
| Статичне відтворення | Response example: `CarPatchResponse`; `Prefer: code=200, example=CarPatchResponse`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method PATCH -Path '/cars/car-example' -Status 200 -Role administrator -Example CarPatchResponse -RequestExample CarPatch
```

### POS-034. Повернення прихованого автомобіля

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-16; REQ-F-071, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-071-01; BDD-014 (повернення) |
| Передумови SRS | А; у незалежній фікстурі car-example вже hidden=true; наявні бронювання й службові періоди збережені. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `PATCH /api/v1/cars/car-example`. `{"hidden":false}`; request example: `CarRestoreRequest`. |
| Очікування SRS | 200; car.hidden=false, warnings=[], futureBookingsCount=1. За SRS авто знову в каталозі зі старими зв’язками; це не перевіряється послідовністю mock-запитів. |
| Статичне відтворення | Response example: `CarRestored`; `Prefer: code=200, example=CarRestored`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method PATCH -Path '/cars/car-example' -Status 200 -Role administrator -Example CarRestored -RequestExample CarRestoreRequest
```

### POS-035. Фізичне видалення авто без зв’язків

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-17; REQ-F-072, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-072-01 (дозволений випадок) |
| Передумови SRS | А; окреме car-unused не має жодного бронювання або службового періоду, включно з історичними; це не car-example інших сценаріїв. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `DELETE /api/v1/cars/car-unused`. Без тіла. |
| Очікування SRS | 204; порожнє тіло. За SRS авто фізично вилучається; повторний GET не використовується як доказ стану mock. |
| Статичне відтворення | Без response example (204); `Prefer: code=204`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method DELETE -Path '/cars/car-unused' -Status 204 -Role administrator
```

## Службова недоступність

### POS-036. Перегляд майбутніх та історичних службових періодів

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-18; REQ-F-074, REQ-F-081, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-074-01, AC-F-081-01; допоміжне читання історії |
| Передумови SRS | А; фікстура містить майбутній period-example та історичний period-history, обидва належать car-example. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/cars/car-example/service-unavailabilities`. Без тіла. |
| Очікування SRS | 200; ServicePeriodList з обома записами, їх межами й причинами; історичний запис не зникає після початку. |
| Статичне відтворення | Response example: `ServicePeriodHistoryList`; `Prefer: code=200, example=ServicePeriodHistoryList`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars/car-example/service-unavailabilities' -Status 200 -Role administrator -Example ServicePeriodHistoryList
```

### POS-037. Перегляд майбутнього службового періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-19; REQ-F-074, REQ-F-075, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-074-01, AC-F-075-01; допоміжне читання для редагування |
| Передумови SRS | А; period-example належить car-example, ще не почався. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/cars/car-example/service-unavailabilities/period-example`. Без тіла. |
| Очікування SRS | 200; ServicePeriod з id/carId, обома межами, timezone і службовою причиною. |
| Статичне відтворення | Response example: `ServicePeriod`; `Prefer: code=200, example=ServicePeriod`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars/car-example/service-unavailabilities/period-example' -Status 200 -Role administrator -Example ServicePeriod
```

### POS-038. Перегляд незмінної історії службового періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-19; REQ-F-074, REQ-F-081, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-081-01 |
| Передумови SRS | А; period-history з 2026-11-01T09 до 2026-11-02T09 вже почався й завершився до контрольованого часу. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `GET /api/v1/cars/car-example/service-unavailabilities/period-history`. Без тіла. |
| Очікування SRS | 200; історичні межі й причина збережені; лише читання, без спроби PATCH/DELETE. |
| Статичне відтворення | Response example: `ServicePeriodHistorical`; `Prefer: code=200, example=ServicePeriodHistorical`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method GET -Path '/cars/car-example/service-unavailabilities/period-history' -Status 200 -Role administrator -Example ServicePeriodHistorical
```

### POS-039. Створення службового періоду суміжно з іншим

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-20; REQ-F-073, REQ-F-074, REQ-F-077, REQ-F-078, REQ-F-079, REQ-F-080, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-073-01, AC-F-074-01, AC-F-080-01; BDD-015 (дозволена суміжність) |
| Передумови SRS | А; новий початок 2026-11-20T09 у майбутньому; існуючий службовий період завершується рівно тоді. Немає інших перетинів із бронюваннями або службовими періодами; обидві межі однозначні. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `POST /api/v1/cars/car-example/service-unavailabilities`. `{"startsAt":"2026-11-20T09","endsAt":"2026-11-21T09","reason":"Планове технічне обслуговування."}`; request example: `ServicePeriodCreateRequest`. |
| Очікування SRS | 201; точні межі/причина, id=period-example, timezone=Europe/Kyiv; у системі коректний Location. Суміжність дозволена, наявні бронювання не скасовуються; mock цього не перевіряє. |
| Статичне відтворення | Response example: `ServicePeriod`; `Prefer: code=201, example=ServicePeriod`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method POST -Path '/cars/car-example/service-unavailabilities' -Status 201 -Role administrator -Example ServicePeriod -RequestExample ServicePeriodCreateRequest
```

### POS-040. Редагування майбутнього службового періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-21; REQ-F-074, REQ-F-075, REQ-F-077, REQ-F-078, REQ-F-079, REQ-F-080, REQ-F-081, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-075-01, AC-F-080-01; BDD-015 (правило суміжності) |
| Передумови SRS | А; period-example ще не почався, належить car-example; нове завершення 2026-11-22T09 збігається з початком іншого періоду. Після PATCH немає перетинів, початок лишається майбутнім. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `PATCH /api/v1/cars/car-example/service-unavailabilities/period-example`. `{"endsAt":"2026-11-22T09"}`; request example: `ServicePeriodPatch`. |
| Очікування SRS | 200; endsAt=2026-11-22T09, startsAt та reason незмінні. За SRS підсумковий період зберігається й суміжність дозволена; mock не змінює фікстуру. |
| Статичне відтворення | Response example: `ServicePeriodUpdated`; `Prefer: code=200, example=ServicePeriodUpdated`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method PATCH -Path '/cars/car-example/service-unavailabilities/period-example' -Status 200 -Role administrator -Example ServicePeriodUpdated -RequestExample ServicePeriodPatch
```

### POS-041. Видалення майбутнього службового періоду

| Поле | Підготовлений сценарій |
| --- | --- |
| Операція та вимоги | OP-22; REQ-F-076, REQ-F-081, REQ-F-087, REQ-F-088, REQ-F-089 |
| Основа AC/BDD | AC-F-076-01 (до початку) |
| Передумови SRS | А; окремо підготовлений period-example належить car-example; поточний час строго до 2026-11-20T09. |
| Роль / mock-заголовок | Адміністратор; Authorization: Bearer mock-administrator |
| Запит | `DELETE /api/v1/cars/car-example/service-unavailabilities/period-example`. Без тіла. |
| Очікування SRS | 204; порожнє тіло. За SRS період усувається; жоден наступний статичний список не використовується як доказ видалення. |
| Статичне відтворення | Без response example (204); `Prefer: code=204`. Не підтверджує виконання бізнес-передумов. |

```powershell
Invoke-PositiveMock -Method DELETE -Path '/cars/car-example/service-unavailabilities/period-example' -Status 204 -Role administrator
```

## Повнота підготовки та межі

Підготовлено **41 незалежний позитивний сценарій** для **22 з 22 операцій**. Рольові варіанти спільних OP-01, OP-02, OP-03, OP-05, OP-11, OP-12 та OP-13 наведено окремо. OP-06–OP-10 належать лише К, OP-14–OP-22 — лише А; чужі рольові виклики тут не додаються як позитивні.

| OP-ID | Підготовлені POS-ID |
| --- | --- |
| OP-01 | POS-001, POS-002, POS-003, POS-004, POS-005 |
| OP-02 | POS-006, POS-007 |
| OP-03 | POS-008, POS-009, POS-010 |
| OP-04 | POS-011 |
| OP-05 | POS-012, POS-013 |
| OP-06 | POS-014 |
| OP-07 | POS-015 |
| OP-08 | POS-016 |
| OP-09 | POS-017 |
| OP-10 | POS-018 |
| OP-11 | POS-019, POS-020 |
| OP-12 | POS-021, POS-022, POS-023, POS-024, POS-025, POS-026 |
| OP-13 | POS-027, POS-028, POS-029 |
| OP-14 | POS-030 |
| OP-15 | POS-031 |
| OP-16 | POS-032, POS-033, POS-034 |
| OP-17 | POS-035 |
| OP-18 | POS-036 |
| OP-19 | POS-037, POS-038 |
| OP-20 | POS-039 |
| OP-21 | POS-040 |
| OP-22 | POS-041 |

Доповнено лише named examples і їх прив’язки; PATCH профілю та службового періоду отримали окремі повторно використовувані response-компоненти з тими самими схемами й статусами, щоб статичне тіло відповідало переданому оновленню. Контрактні схеми, методи, URI, коди й бізнес-правила не змінено. Для поточної версії повторюється лише офлайн-валідація OpenAPI та examples; це не виконання POS.

Строк сесії, наслідки зміни пароля для сесій і календарне питання Q-07 залишаються відкритими. У цих фікстурах використано однозначні місцеві межі; правила для проблемних проміжних обчислень не вигадуються. Виконання POS і фіксацію результатів залишено для пункту 13; негативні сценарії та API-GATE не виконано. Результатів PASS/FAIL для POS у цьому документі немає.
