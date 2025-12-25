# API "Автоклиент" ПриватБанка (v3.0.0)

Краткое справочное руководство по API для взаимодействия с серверной частью приложения «Автоклиент».

---

### Важлива інформація!

> -   **Безпека токена:** Не передавайте токен третім особам.
> -   **Протоколи:** tls 1.0 та 1.1 не підтримуються. Рекомендується використовувати tls 1.3.
> -   **Доступність:** Сервіс доступний для юридичних осіб в тарифах “Бізнес Комфорт” та “Бізнес Про”. Для ФОП сервіс доступний в будь-якому тарифі.

---

## 1. Авторизація

Для отримання авторизаційних даних (`token`) необхідно підключити додаток «Інтеграція (Автоклієнт)» в інтерфейсі "Приват24 для бізнесу".

1.  У "Приват24 для бізнесу" перейти в налаштування та підключити додаток API.
2.  Вказати назву та, за потреби, IP-адреси.
3.  Після створення перейти в налаштування додатка та скопіювати `token`.
4.  Існує можливість отримати дані в старому форматі (окремо `ID` та `token`).

### Взаємодія з API

Усі запити повинні містити обов’язкові поля в **header**:

-   `User-Agent`: Назва клієнтського додатка.
-   `token`: Ваш авторизаційний токен.
-   `Content-Type`: `application/json;charset=cp1251`.
-   **Кодування:** Підтримуються `utf8` та `cp1251` (за замовчуванням `cp1251`, якщо `charset` не вказано).

---

## 2. Баланси та транзакції за рахунками

Запити надсилаються методом `GET`. Базовий URL: `https://acp.privatbank.ua/api/statements`

---

## Reference: Legacy PHP snippets (useful implementation hints)

Below are PHP excerpts from a legacy project that show practical details and edge-cases for working with the PrivatBank Autoclient API.

### 1) API health/status check

Summary: call `/settings` and ensure `status == 'SUCCESS'`, `settings.phase == 'WRK'` and `settings.work_balance == 'N'` before making heavy requests.

```php
/* 
    ПЕРЕВІРКА СТАТУСУ API
    якщо work_balance != "N", запити робити не можна
    якщо phase != "WRK", то в цей період запити до API можуть повертатися з помилками
*/
function CHEK_PRIVAT_API()
{
    $ApiQuery = 'https://acp.privatbank.ua/api/statements/settings';
    $answer = GET_PRIVAT_API($ApiQuery);

    //Обробка відповіді
    if ($answer['status'] == 'SUCCESS') {
        if ($answer['settings']['phase'] == 'WRK') {
            if ($answer['settings']['work_balance'] == 'N') {
                return true;
            }
        }
    }
}
```

Notes: The check prevents queries during maintenance or restricted periods.

### 2) HTTP headers and request pattern

Legacy code shows example cURL headers used in the project:

```php
// Параметры подключения к API Привата
$cid = VAR_CUR_PRIVAT_USER_ID; // id владельца с Автоклиента
$token = VAR_CUR_PRIVAT_USER_TOKEN1 . VAR_CUR_PRIVAT_USER_TOKEN2; // token владельца с Автоклиента

//Запит на API Привата (example)
CURLOPT_HTTPHEADER => array(
    'User-Agent: PostmanRuntime/7.26.8',
    'Accept-Encoding: gzip, deflate, br',
    'Content-Type: application / json; charset = cp1251',
    'id: ' . $cid,
    'token: ' . $token
),
```

Notes: the API expects `token` and often `id` (client id) headers as used by Autoclient.

### 3) Transactions import (paginated)

Core flow (simplified):

- Determine `startDate` (either stored constant, or last transaction date saved)
- Loop: call `/statements/transactions?startDate=DD-MM-YYYY&followId={next}`
- For each page: iterate `transactions[]`, check or create a counterparty record, prepare transaction payload, then insert or update local record keyed by `TECHNICAL_TRANSACTION_ID` (unique identifier)
- If `exist_next_page` true, repeat using `next_page_id` as `followId`.

Excerpt (essential logic):

```php
// Приват: Отримання нових Транзакцій по рахункам
function GET_TRANSACTIONS()
{
    // determine $d_start
    do {
        $ApiUrl = 'https://acp.privatbank.ua/api/statements/transactions?startDate=' . $d_start . '&followId=' . $NextPage;
        $answer = GET_PRIVAT_API($ApiUrl);
        if ($answer['status'] != 'SUCCESS') return $answer['status'];

        foreach ($answer['transactions'] as $result) {
            // check/create counterparty
            // map fields
            // deduplicate by TECHNICAL_TRANSACTION_ID
            // insert or update
        }
        $NextPage = $answer['next_page_id'];
    } while ($answer['exist_next_page'] > 0);
}
```

### 4) Balances and turnovers per account (per-account queries)

Example shows per-account balance queries using `Acc` parameter: `/statements/balance?Acc={acc}&startDate=...&followId=...`

### 5) Currency history

Use `GET /api/proxy/currency/history?startDate=DD-MM-YYYY&endDate=DD-MM-YYYY` and process `data.history`.

---

Use these snippets as an implementation reference: they show practical header usage, pagination, and data fields mapping. Integrations in Python should follow the same logic (check API status, use `followId` pagination, deduplicate by `TECHNICAL_TRANSACTION_ID`, update or create counterparties, and update `last_import_date` for incrementality).

### 2.1. Отримання серверних дат

-   **Endpoint:** `/settings`
-   **Призначення:** Отримати службові дати (поточний/минулий операційний день, дата підсумкової виписки) та статус роботи сервера.
-   **Важливо:** Якщо `phase` не дорівнює `WRK`, запити до API можуть повертати помилки.

### 2.2. Отримання балансів та транзакцій

-   **Баланси:** `/balance`
-   **Транзакції:** `/transactions`

#### Параметри запиту:

-   `acc`: Номер рахунку. Якщо не вказано, дані формуються по всім активним рахункам.
-   `startDate`: Дата початку (`ДД-ММ-ГГГГ`), обов'язковий.
-   `endDate`: Дата закінчення (`ДД-ММ-ГГГГ`), необов'язковий.
-   `followId`: ID наступної "пачки" даних з попередньої відповіді (для пагінації).
-   `limit`: Кількість записів (за замовчуванням 20, максимум 500).

#### Інші ендпоінти:

-   **Проміжні дані (з `lastday` по `today`):** `/balance/interim` або `/transactions/interim`
-   **Дані за останній підсумковий день:** `/balance/final` або `/transactions/final`

**Пагінація:** Якщо у відповіді `exist_next_page: true`, значення з `next_page_id` потрібно передати в наступний запит у параметр `followId`.

---

## 3. Курси валют

-   **Поточні курси:** `GET https://acp.privatbank.ua/api/proxy/currency/`
-   **Історія курсів:** `GET https://acp.privatbank.ua/api/proxy/currency/history?startDate=ДД-ММ-ГГГГ&endDate=ДД-ММ-ГГГГ` (період не більше 15 днів).

#### Поля відповіді:
-   `B`: Купівля.
-   `S`: Продаж.
-   `rate`: Курс.
-   `nbuRate`: Курс НБУ.

---

## 4. Створення платежу

-   **Endpoint (з прогнозом):** `POST https://acp.privatbank.ua/api/proxy/payment/create_pred`
-   **Endpoint (без прогнозу):** `POST https://acp.privatbank.ua/api/proxy/payment/create`

Тіло запиту (`BODY`) - JSON-об'єкт з реквізитами платежу.

#### Обов’язкові реквізити:
-   `document_number`: Номер документа.
-   `payer_account`: Рахунок відправника.
-   `recipient_account`: Рахунок одержувача (або `recipient_card` для платежу на картку).
-   `recipient_nceo`: ЄДРПОУ одержувача.
-   `payment_naming`: Назва одержувача.
-   `payment_amount`: Сума платежу.
-   `payment_destination`: Призначення платежу (5-420 символів, для податкових - до 140).

Успішна відповідь повертає `HTTP 201` та JSON з `payment_ref` та `payment_pack_ref`.

### 4.1. Завантаження підписаного платежу

Процес складається з двох кроків:
1.  **Отримання інформації по платежу:**
    -   `GET /api/proxy/payment/get?ref={референсПлатежу}`
    -   У відповіді будуть дані платежу та блок `fields_for_sign`, що містить перелік полів для підпису.
2.  **Відправка підпису на збереження:**
    -   `POST /api/proxy/payment/add-sign?ref={референсПлатежу}`
    -   **Body:** `{"sign": "BASE64-представлення підписаних даних"}`
    -   Сигнатуру необхідно накласти на JSON-відповідь з першого кроку.
    -   **Важливо:** Для кожного рівня підпису (директор, бухгалтер) потрібно використовувати токени відповідних відповідальних осіб.

### 4.2. Створення валютних платежів

-   **SWIFT:** `POST https://acp.privatbank.ua/api/proxy/zed/swift/save_with_forecast`
-   **Внутрішні валютні:** `POST https://acp.privatbank.ua/api/proxy/zed/cpi/save_with_forecast`

Тіло запиту містить деталізовану інформацію про платника, отримувача, банки-кореспонденти та сам платіж.

---

## 5. Електронний документообіг (Інвойсинг)

Базовий URL: `https://acp.privatbank.ua`

### 5.1. Журнал документів

-   **Endpoints:**
    -   `/api/proxy/edoc/journal/inbox` (Вхідні)
    -   `/api/proxy/edoc/journal/outbox` (Вихідні)
    -   `/api/proxy/edoc/journal/in-process` (В роботі)
    -   `/api/proxy/edoc/journal/all` (Всі)
    -   `/api/proxy/edoc/journal/to-pay` (До сплати)
-   **Метод:** `POST`
-   **Параметри:** `dateBegin`, `dateEnd` (обов'язкові), а також багато необов'язкових для фільтрації та сортування (`okpo`, `limit`, `docType`, `status`, `sortBy` та ін.).

### 5.2. Завантаження та робота з документами

API дозволяє завантажувати документи в різних форматах (XML, PDF, Base64), з підписом (ЕЦП) та без, а також керувати ними.

-   **Завантаження XML (без ЕЦП):** `POST /api/proxy/edoc/loader/upload`
-   **Завантаження підписаного XML:** `POST https://docs.24.privatbank.ua/loader/v2/upload-signed-xml`
-   **Завантаження PDF (без ЕЦП):** `POST /api/proxy/edoc/loader/upload-pdf`
-   **Отримання документа (XML/PDF/Base64/p7s):** `GET /api/proxy/edoc/journal/get-xml-document/{ID}?okpo={okpo}`
-   **Видалення документа:** `GET /api/proxy/edoc/journal/delete/{ID}?okpo={okpo}`
-   **Створення платежу на основі рахунка:** `POST /api/proxy/edoc/create-payment-from-invoice/{ID}?okpo={okpo}&payerAccount={payerAccount}`

---

## 6. Зарплатний проєкт

API для управління зарплатними проектами, групами, співробітниками та відомостями.

-   **Отримати список груп (проєктів):** `GET /api/pay/mp/list-groups`
-   **Отримати список одержувачів у групі:** `GET /api/pay/mp/list-receivers?group={код_групи}`
-   **Додати/оновити співробітника:** `POST /api/pay/mp/update-receiver`
-   **Отримати список відомостей:** `GET /api/pay/apay24/packets/list`
-   **Створити нову відомість:** `POST /api/pay/maspay/create`
-   **Додати співробітника у відомість:** `POST /api/pay/maspay/{референс_пакета}/add`
-   **Надіслати відомість на перевірку:** `POST /api/pay/maspay/{референс_пакета}/validate`

---

## 7. Корпоративні картки

-   **Зведена інформація по всім карткам:** `POST /api/corpcards/v2/cards/list`
-   **Виписка за групою карток:** `POST /api/corpcards/v2/corp/statements?dateStart={date}&dateEnd={date}`
-   **Виписка за карткою:** `POST /api/corpcards/v2/card/statements?dateStart={date}&dateEnd={date}`

---

## 8. Сервіс перевірки контрагентів (УБКІ)

-   **Endpoint:** `POST https://acp.privatbank.ua/api/ubki/check`
-   **Призначення:** Надає детальну інформацію про контрагента (юр. особу або ФОП) з державних реєстрів, а також попередження про ризики (банкрутство, борги, санкції тощо).
-   **Запит:** `{"edrpou": "ЄДРПОУ/ІПН контрагента"}`

---

## 9. Отримання квитанцій та виписок

-   **Квитанції по платежам (PDF):**
    -   **Endpoint:** `POST https://acp.privatbank.ua/api/paysheets/print_receipt`
    -   **Body:** `{"transactions": [{"account": "...", "reference": "...", "refn": "..."}], "perPage": 4}`
-   **Еквайрингова виписка (по терміналам):**
    -   **Endpoint:** `POST https://acp.privatbank.ua/api/equiring/statements`
    -   **Body:** `{"account": "...", "dateFrom": "YYYY-MM-DD", "dateTo": "YYYY-MM-DD"}`
    -   **Примітка:** Різниця між `dateFrom` та `dateTo` не може бути більше 1 дня.

---

## 10. Пример реализации (PHP)

*Ниже приведены примеры из реального рабочего проекта на PHP для демонстрации логики взаимодействия с API.*

### Проверка статуса API

```php
/* 
    ПЕРЕВІРКА СТАТУСУ API
    якщо work_balance != "N", запити робити не можна
    якщо phase != "WRK", то в цей період запити до API можуть повертатися з помилками
*/
function CHEK_PRIVAT_API()
{
    $ApiQuery = 'https://acp.privatbank.ua/api/statements/settings';
    $answer = GET_PRIVAT_API($ApiQuery);

    //Обробка відповіді
    if ($answer['status'] == 'SUCCESS') {
        if ($answer['settings']['phase'] == 'WRK') {
            if ($answer['settings']['work_balance'] == 'N') {
                return true;
            }
        }
    }
}
```

### Основная функция GET-запроса

```php
function GET_PRIVAT_API($ApiUrl)
{
    //Параметры подключения к API Привата
    $cid = '...'; // id владельца с Автоклиента
    $token = '...'; // token владельца с Автоклиента

    //Запит на API Привата
    $curl = curl_init();
    curl_setopt_array($curl, array(
        CURLOPT_URL => $ApiUrl,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_ENCODING => 'gzip',
        CURLOPT_TIMEOUT => 0,
        CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
        CURLOPT_CUSTOMREQUEST => 'GET',
        CURLOPT_HTTPHEADER => array(
            'User-Agent: PostmanRuntime/7.26.8',
            'Content-Type: application/json; charset=cp1251',
            'id: ' . $cid,
            'token: ' . $token
        ),
    ));

    //Отримання і обробка відповіді
    $response = iconv("windows-1251", "UTF-8", curl_exec($curl));
    curl_close($curl);
    
    return json_decode($response, true);
}
```

### Получение транзакций с пагинацией

```php
function GET_TRANSACTIONS()
{
    // ... визначення startDate ...
  
    $NextPage = '';
    do {
        $ApiUrl =
            'https://acp.privatbank.ua/api/statements/transactions?' .
            'startDate=' . $d_start . '&followId=' . $NextPage;
        $answer = GET_PRIVAT_API($ApiUrl);
      
        if ($answer['status'] != 'SUCCESS') {
            break;
        }

        foreach ($answer['transactions'] as $result) {
            // ... логіка перевірки на дублікат по TECHNICAL_TRANSACTION_ID ...
            
            // ... маппинг полів з $result в поля бази даних ...

            // ... створення або оновлення запису ...
        }
        
        // Наступна пачка
        $NextPage = $answer['next_page_id'];
    } while ($answer['exist_next_page'] > 0);
}
```
