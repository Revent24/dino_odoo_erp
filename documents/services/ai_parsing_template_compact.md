# Парсинг документа

**Задача:** Розпізнай документ і поверни JSON.

## Правила

1. **Постачальник** = хто ПРОДАЄ (не покупець!)
2. **Кількість/одиниці** з окремих колонок (НЕ з назви!)
3. **Копіюй числа як є** (не рахуй): quantity, price_unit, price_subtotal, price_total
4. **МФО** = 5-10 символи IBAN (UA**293005**28... → "300528")
5. **Якщо немає** → null
6. **Очищення:** артикули без спецсимволів, УКТ ЗЕД тільки цифри

## JSON

```json
{
  "header": {
    "doc_type": "string|null", "doc_number": "string|null", "doc_date": "YYYY-MM-DD|null",
    "vendor_name": "string|null", "vendor_edrpou": "8-10 digits|null", "vendor_ipn": "string|null",
    "vendor_address": "string|null", "vendor_iban": "UA...|null", "vendor_mfo": "6 digits|null",
    "vendor_bank": "string|null", "currency": "UAH",
    "amount_untaxed": "number", "tax_percent": "0|20", "amount_tax": "number", "amount_total": "number"
  },
  "lines": [{
    "line_number": 1, "name": "string", "quantity": "number", "unit": "string",
    "price_unit": "number|null", "price_unit_with_tax": "number|null",
    "price_subtotal": "number|null", "price_total": "number|null",
    "article": "string|null", "ukt_zed": "digits|null", "description": "string|null"
  }]
}
```

## Приклад

**Вхід:** `Лист 0.8 | 79.36 кг | 75.52 | 5993.27`

**Вихід:**
```json
{"lines": [{"name": "Лист 0.8", "quantity": 79.36, "unit": "кг", "price_unit": 75.52, "price_subtotal": 5993.27}]}
```
