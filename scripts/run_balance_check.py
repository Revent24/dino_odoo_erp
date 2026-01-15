#
#  -*- File: scripts/run_balance_check.py -*-
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import odoo

def run_balance_check():
    # 'env' is globally available in odoo shell
    bank = env['dino.bank'].search([('mfo', '=', '305299')], limit=1)
    if not bank:
        print("ОШИБКА: Запись ПриватБанка с МФО 305299 не найдена.")
        return

    if not bank.api_key:
        print("ОШИБКА: API Key (Token) не установлен.")
        return

    try:
        from odoo.addons.dino_erp.api_integration.services.privat_client import PrivatClient
        
        client = PrivatClient(api_key=bank.api_key, client_id=bank.api_client_id)
        
        # --- Шаг 1: Получаем stdate ---
        print("Получаем stdate из настроек API...")
        settings_response = client.get_api_settings()
        if not (settings_response and settings_response.get('status') == 'SUCCESS'):
            print("ОШИБКА: Не удалось получить stdate. Проверка Шага 1 не пройдена.")
            return
            
        stdate = (settings_response.get('settings') or {}).get('date_final_statement')
        if not stdate:
            print("ОШИБКА: stdate не найдена в ответе API.")
            return
        
        # API возвращает дату в формате 'DD.MM.YYYY HH:MM:SS', нам нужна 'DD-MM-YYYY'
        stdate_formatted = stdate.split(' ')[0].replace('.', '-')
        print(f"Используем stdate: {stdate_formatted}")

        # --- Шаг 2: Запрос балансов ---
        print("\nВыполняется Шаг 2: вызов GET /api/statements/balance...")
        balances_response = client.fetch_balances_for_all_accounts(startDate=stdate_formatted)
        
        print("\n--- Результат Шага 2 (Балансы) ---")
        if balances_response:
            # balances_response это уже готовый список
            print(json.dumps(balances_response, indent=2, ensure_ascii=False))
        else:
            print("ОШИБКА: Не удалось получить балансы или API вернул пустой список.")
        print("---------------------------------")

    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")

run_balance_check()
# End of file scripts/run_balance_check.py
