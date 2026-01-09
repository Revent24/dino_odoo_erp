# AI Parsing Template (Compact Version)

## Instructions

**Task:** Parse Ukrainian accounting document and return JSON.

### Key Rules

1. **Vendor** = WHO SELLS / issued the invoice (NOT the buyer!)

2. **Quantity and Unit** = from SEPARATE columns (NOT from product name!)
   - Example: "Sheet stainless 201 0.8 | 79.36 | kg"
   - Result: quantity=79.36, unit="kg", name="Sheet stainless 201 0.8"
   - WARNING: 0.8 in the name is a characteristic (thickness), NOT quantity!

3. **Extract numbers as-is** - copy from document, calculations will be verified later
   - Read quantity, price_unit, price_subtotal, price_total AS SHOWN in document
   - Don't calculate - just copy the numbers you see
   - IMPORTANT: Not all price fields will be in document:
     * Some documents have only price_unit (without VAT)
     * Some have only price_unit_with_tax (with VAT)
     * Some have both - extract both if visible
     * Same for price_subtotal and price_total - copy what you see
   
4. **MFO** = characters 5-10 from IBAN
   - Example: UA**293005**280000... → MFO = "300528"

5. **DON'T make up data** - if not in document → null

6. **Cleaning:**
   - Remove special chars from articles: X/, *, #
   - UKT ZED - digits only, no spaces
   - Units - as in original ("pc", "100 pc", "m")

## JSON Schema

```json
{
  "header": {
    "doc_type": "string or null",
    "doc_number": "string or null",
    "doc_date": "YYYY-MM-DD or null",
    "vendor_name": "string or null",
    "vendor_edrpou": "string (8-10 digits) or null",
    "vendor_ipn": "string or null",
    "vendor_address": "string or null",
    "vendor_iban": "string (UA...) or null",
    "vendor_mfo": "string (6 digits from IBAN pos 5-10) or null",
    "vendor_bank": "string or null",
    "currency": "UAH",
    "amount_untaxed": "number (without VAT)",
    "tax_percent": "0 or 20",
    "amount_tax": "number (VAT amount)",
    "amount_total": "number (total to pay)"
  },
  "lines": [
    {
      "line_number": "integer",
      "name": "string (name WITHOUT quantity/unit)",
      "quantity": "number",
      "unit": "string (as in document)",
      "price_unit": "number (without VAT) or null",
      "price_unit_with_tax": "number (with VAT) or null",
      "price_subtotal": "number (without VAT) or null",
      "price_total": "number (with VAT) or null",
      "article": "string or null",
      "ukt_zed": "string (digits only) or null",
      "description": "string or null (additional notes about this line)"
    }
  ]
}
```

## Example

**Input:**
```
Product: Sheet stainless 201 0.8 (1.25x2.5)
Quantity: 79.36 kg
Price without VAT: 75.52
Sum: 5993.27
```

**Output:**
```json
{
  "lines": [{
    "name": "Sheet stainless 201 0.8 (1.25x2.5)",
    "quantity": 79.36,
    "unit": "kg",
    "price_unit": 75.52,
    "price_subtotal": 5993.27,
    "price_total": 7191.92
  }]
}
```
