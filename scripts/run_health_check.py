#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import odoo

def run_health_check():
    # 'env' is globally available in odoo shell
    # Find the PrivatBank record
    bank = env['dino.bank'].search([('mfo', '=', '305299')], limit=1) # Using MFO for PrivatBank
    if not bank:
        print("ОШИБКА: Запись ПриватБанка с МФО 305299 не найдена в Odoo.")
        return

    if not bank.api_key:
        print("ОШИБКА: API Key (Token) не установлен для ПриватБанка.")
        return

    # Import the client and run the check
    try:
        from odoo.addons.dino_erp.finance.services.privat_client import PrivatClient
        
        print("Инициализация PrivatClient...")
        client = PrivatClient(api_key=bank.api_key, client_id=bank.api_client_id)
        
        print("Выполняется Шаг 1 (Health Check): вызов GET /api/statements/settings...")
        settings_response = client.get_api_settings()
        
        print("\n--- Результат Health Check ---")
        if settings_response:
            print(json.dumps(settings_response, indent=2, ensure_ascii=False))
        else:
            print("ОШИБКА: Не удалось получить ответ от API.")
        print("--------------------------")

    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")

# This part will be executed when the script is fed into odoo shell
run_health_check()
