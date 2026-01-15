#
#  -*- File: documents/scripts/debug_ai_parser.py -*-
#
import sys
import json

# Добавляем корень модуля в sys.path
sys.path.append('/home/steve/OdooApps/odoo_projects/dino24_addons/dino_erp')

from documents.services.ai_parser_service import GoogleGeminiParser, OpenRouterParser

sample_text = """
Поставщик: Тест ООО
Номер: 123
Дата: 2026-01-01
Товары:
1. Ручка; 10; 5.0
2. Блокнот; 5; 20.0
"""

print('== Debug GoogleGeminiParser.parse (debug_only=True) ==')
res = GoogleGeminiParser.parse(text=sample_text, api_key='DUMMY_KEY', model_name='gemini-2.0-flash-exp', debug_only=True)
print(json.dumps(res, indent=2, ensure_ascii=False))

print('\n== Debug OpenRouterParser.parse (debug_only=True) ==')
# OpenRouterParser may expect different kwargs; we pass api_key and model_name as well
try:
    res2 = OpenRouterParser.parse(text=sample_text, api_key='DUMMY_KEY', model_name='google/gemini-2.0-flash-exp', debug_only=True)
    print(json.dumps(res2, indent=2, ensure_ascii=False))
except Exception as e:
    print('OpenRouterParser error:', e)
# End of file documents/scripts/debug_ai_parser.py
