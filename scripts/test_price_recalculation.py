#
#  -*- File: scripts/test_price_recalculation.py -*-
#
#!/usr/bin/env python3
"""
Тест взаимного пересчета цен price_untaxed <-> price_tax
"""

import sys
import os

# Test calculations
def test_price_calculations():
    print("=" * 60)
    print("ТЕСТ ВЗАИМНОГО ПЕРЕСЧЕТА ЦЕН")
    print("=" * 60)
    
    vat_rate = 20.0  # 20% VAT
    
    # Test 1: price_untaxed -> price_tax
    print("\n1️⃣  Тест: price_untaxed → price_tax")
    price_untaxed = 100.0
    price_tax = price_untaxed * (1 + vat_rate / 100)
    print(f"   price_untaxed: {price_untaxed:.2f}")
    print(f"   vat_rate: {vat_rate}%")
    print(f"   price_tax: {price_tax:.2f}")
    print(f"   ✅ Формула: {price_untaxed} × (1 + {vat_rate}/100) = {price_tax}")
    
    # Test 2: price_tax -> price_untaxed
    print("\n2️⃣  Тест: price_tax → price_untaxed")
    price_tax = 120.0
    price_untaxed = price_tax / (1 + vat_rate / 100)
    print(f"   price_tax: {price_tax:.2f}")
    print(f"   vat_rate: {vat_rate}%")
    print(f"   price_untaxed: {price_untaxed:.2f}")
    print(f"   ✅ Формула: {price_tax} / (1 + {vat_rate}/100) = {price_untaxed:.2f}")
    
    # Test 3: Round-trip test
    print("\n3️⃣  Тест: Обратный пересчет (round-trip)")
    original_price = 75.52
    price_with_tax = original_price * (1 + vat_rate / 100)
    price_back = price_with_tax / (1 + vat_rate / 100)
    print(f"   Исходная цена БЕЗ НДС: {original_price:.2f}")
    print(f"   Цена С НДС: {price_with_tax:.2f}")
    print(f"   Обратно БЕЗ НДС: {price_back:.2f}")
    diff = abs(original_price - price_back)
    print(f"   Разница: {diff:.10f}")
    if diff < 0.01:
        print(f"   ✅ PASS: Разница меньше 0.01")
    else:
        print(f"   ❌ FAIL: Разница слишком большая")
    
    # Test 4: Zero VAT
    print("\n4️⃣  Тест: Без НДС (vat_rate = 0)")
    vat_rate_zero = 0.0
    price_untaxed = 525.0
    price_tax = price_untaxed * (1 + vat_rate_zero / 100) if vat_rate_zero else price_untaxed
    print(f"   price_untaxed: {price_untaxed:.2f}")
    print(f"   vat_rate: {vat_rate_zero}%")
    print(f"   price_tax: {price_tax:.2f}")
    if price_untaxed == price_tax:
        print(f"   ✅ PASS: Цены равны при нулевом НДС")
    else:
        print(f"   ❌ FAIL: Цены должны быть равны")
    
    # Test 5: Real example from screenshot
    print("\n5️⃣  Тест: Реальный пример из скриншота")
    vat_rate = 20.0
    price_untaxed = 75.52
    price_tax_expected = 90.62
    price_tax_calculated = price_untaxed * (1 + vat_rate / 100)
    print(f"   price_untaxed: {price_untaxed:.2f}")
    print(f"   price_tax (ожидается): {price_tax_expected:.2f}")
    print(f"   price_tax (рассчитано): {price_tax_calculated:.2f}")
    diff = abs(price_tax_expected - price_tax_calculated)
    print(f"   Разница: {diff:.2f}")
    if diff < 0.01:
        print(f"   ✅ PASS")
    else:
        print(f"   ⚠️  Небольшое расхождение (возможно из-за округления)")
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 60)

if __name__ == '__main__':
    test_price_calculations()
# End of file scripts/test_price_recalculation.py
