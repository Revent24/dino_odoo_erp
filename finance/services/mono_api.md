# Monobank Personal API

Справочное руководство по API monobank для личного использования.

---

## 1. Інформація про клієнта

Отримання інформації про клієнта, переліку його рахунків та "банок".

-   **Обмеження:** Не частіше ніж 1 раз на 60 секунд.

### Запит

-   **Метод:** `GET`
-   **Endpoint:** `/personal/client-info`
-   **Базовий URL:** `https://api.monobank.ua`

#### Заголовки (Headers)

-   **`X-Token`** (string, required): Ваш особистий токен доступу до API.

---

### Відповідь (200 OK)

Успішна відповідь повертає JSON-об'єкт з інформацією про клієнта.

#### Схема відповіді

-   **`clientId`** (string): Ідентифікатор клієнта.
-   **`name`** (string): Ім’я клієнта.
-   **`webHookUrl`** (string): URL для отримання вебхуків про зміни балансу.
-   **`permissions`** (string): Рядок з переліком прав доступу, наданих токену (1 літера = 1 право).
-   **`accounts`** (array of objects): Масив об'єктів з інформацією про рахунки клієнта.
    -   `id` (string): Ідентифікатор рахунку.
    -   `sendId` (string): Ідентифікатор для швидких переказів через `send.monobank.ua`.
    -   `balance` (integer): Баланс у мінімальних одиницях валюти (копійках, центах).
    -   `creditLimit` (integer): Кредитний ліміт.
    -   `type` (string): Тип картки (`black`, `white`, `platinum` і т.д.).
    -   `currencyCode` (integer): Код валюти за ISO 4217 (наприклад, `980` для UAH).
    -   `cashbackType` (string): Тип кешбеку (`UAH`, `Miles` тощо).
    -   `maskedPan` (array of strings): Масив маскованих номерів карток.
    -   `iban` (string): Номер рахунку у форматі IBAN.
-   **`jars`** (array of objects): Масив об'єктів з інформацією про "банки".
    -   `id` (string): Ідентифікатор "банки".
    -   `sendId` (string): Ідентифікатор для поповнення через `send.monobank.ua`.
    -   `title` (string): Назва "банки".
    -   `description` (string): Опис.
    -   `currencyCode` (integer): Код валюти.
    -   `balance` (integer): Поточна сума.
    -   `goal` (integer): Цільова сума.

#### Приклад відповіді (JSON)

```json
{
  "clientId": "3MSaMMtczs",
  "name": "Мазепа Іван",
  "webHookUrl": "https://example.com/some_random_data_for_security",
  "permissions": "psfj",
  "accounts": [
    {
      "id": "kKGVoZuHWzqVoZuH",
      "sendId": "uHWzqVoZuH",
      "balance": 10000000,
      "creditLimit": 10000000,
      "type": "black",
      "currencyCode": 980,
      "cashbackType": "UAH",
      "maskedPan": [
        "537541******1234"
      ],
      "iban": "UA733220010000026201234567890"
    }
  ],
  "jars": [
    {
      "id": "kKGVoZuHWzqVoZuH",
      "sendId": "uHWzqVoZuH",
      "title": "На тепловізор",
      "description": "На тепловізор",
      "currencyCode": 980,
      "balance": 1000000,
      "goal": 10000000
    }
  ]
}
```

---

## 2. Отримання курсів валют

Отримання базового переліку курсів валют monobank.

-   **Обмеження:** Інформація кешується та оновлюється не частіше 1 разу на 5 хвилин.

### Запит

-   **Метод:** `GET`
-   **Endpoint:** `/bank/currency`
-   **Базовий URL:** `https://api.monobank.ua`

### Відповідь (200 OK)

Успішна відповідь повертає масив JSON-об'єктів з курсами валют.

#### Схема відповіді (для одного об'єкта в масиві)

-   **`currencyCodeA`** (integer): Код першої валюти в парі (ISO 4217).
-   **`currencyCodeB`** (integer): Код другої валюти в парі (ISO 4217).
-   **`date`** (integer): Час актуальності курсу (Unix time, секунди).
-   **`rateSell`** (float): Курс продажу.
-   **`rateBuy`** (float): Курс купівлі.
-   **`rateCross`** (float): Крос-курс (якщо є).

#### Приклад відповіді (JSON)

```json
[
  {
    "currencyCodeA": 840,
    "currencyCodeB": 980,
    "date": 1552392228,
    "rateSell": 27,
    "rateBuy": 27.2,
    "rateCross": 27.1
  }
]
```

---

## 3. Отримання виписки

Отримання виписки по рахунку або "банці" за вказаний період.

-   **Обмеження:**
    -   Не частіше ніж 1 раз на 60 секунд.
    -   Максимальний період запиту — 31 доба + 1 година (2682000 секунд).
-   **Пагінація:** Метод повертає до 500 останніх транзакцій за вказаний період. Якщо кількість транзакцій дорівнює 500, необхідно зробити наступний запит, встановивши параметр `to` на час (`time`) останньої отриманої транзакції, і повторювати, доки кількість транзакцій не буде меншою за 500.

### Запит

-   **Метод:** `GET`
-   **Endpoint:** `/personal/statement/{account}/{from}/{to}`
-   **Базовий URL:** `https://api.monobank.ua`

#### Параметри шляху (Path Parameters)

-   **`account`** (string, required): Ідентифікатор рахунку/банки (або `0` для дефолтного рахунку).
-   **`from`** (string, required): Початок періоду виписки (Unix time, секунди).
-   **`to`** (string, optional): Кінець періоду виписки (Unix time, секунди). Якщо не вказано, використовується поточний час.

#### Заголовки (Headers)

-   **`X-Token`** (string, required): Ваш особистий токен доступу до API.

---

### Відповідь (200 OK)

Успішна відповідь повертає масив JSON-об'єктів, що представляють транзакції.

#### Схема відповіді (для однієї транзакції)

-   **`id`** (string): Унікальний ID транзакції.
-   **`time`** (integer): Час транзакції (Unix time, секунди).
-   **`description`** (string): Опис транзакції.
-   **`mcc`** (integer): Merchant Category Code (ISO 18245).
-   **`originalMcc`** (integer): Оригінальний MCC.
-   **`hold`** (boolean): Статус блокування суми (`true`/`false`).
-   **`amount`** (integer): Сума у валюті рахунку (в копійках/центах).
-   **`operationAmount`** (integer): Сума у валюті операції (в копійках/центах).
-   **`currencyCode`** (integer): Код валюти рахунку (ISO 4217).
-   **`commissionRate`** (integer): Розмір комісії.
-   **`cashbackAmount`** (integer): Сума кешбеку.
-   **`balance`** (integer): Баланс рахунку після операції.
-   **`comment`** (string, optional): Коментар до переказу.
-   **`receiptId`** (string, optional): ID квитанції для check.gov.ua.
-   **`invoiceId`** (string, optional): ID квитанції ФОПа.
-   **`counterEdrpou`** (string, optional): ЄДРПОУ контрагента (для рахунків ФОП).
-   **`counterIban`** (string, optional): IBAN контрагента (для рахунків ФОП).
-   **`counterName`** (string, optional): Найменування контрагента.

#### Приклад відповіді (JSON)

```json
[
  {
    "id": "ZuHWzqkKGVo=",
    "time": 1554466347,
    "description": "Покупка щастя",
    "mcc": 7997,
    "originalMcc": 7997,
    "hold": false,
    "amount": -95000,
    "operationAmount": -95000,
    "currencyCode": 980,
    "commissionRate": 0,
    "cashbackAmount": 19000,
    "balance": 10050000,
    "comment": "За каву",
    "receiptId": "XXXX-XXXX-XXXX-XXXX",
    "invoiceId": "2103.в.27",
    "counterEdrpou": "3096889974",
    "counterIban": "UA898999980000355639201001404",
    "counterName": "ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ «ВОРОНА»"
  }
]
```


