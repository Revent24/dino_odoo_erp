# TASK: Parse Ukraine doc to JSON.

# RULES:
1. Name: Everything before quantity. Include specs (0.8, 1.25x2.5).
2. Logic: Sequence is usually [Name] -> [Quantity] -> [Unit] -> [Price] -> [Subtotal].
3. Calculations: If Subtotal or VAT is missing - CALCULATE it (Qty * Price).
4. IBAN/MFO: Extract from UA... string. MFO is pos 5-10.
5. Formatting: Return ONLY JSON. Replace newlines in names with spaces.

# JSON Schema:
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
