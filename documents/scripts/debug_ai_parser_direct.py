import sys
# Ensure package root is on sys.path so absolute imports inside module work
sys.path.insert(0, '/home/steve/OdooApps/odoo_projects/dino24_addons/dino_erp')
import json
import importlib.util

# Путь к модулю ai_parser_service.py
module_path = '/home/steve/OdooApps/odoo_projects/dino24_addons/dino_erp/documents/services/ai_parser_service.py'

spec = importlib.util.spec_from_file_location('ai_parser_service_mod', module_path)
ai_mod = importlib.util.module_from_spec(spec)
loader = spec.loader
if loader is None:
    raise SystemExit('Could not load module')
loader.exec_module(ai_mod)

GoogleGeminiParser = getattr(ai_mod, 'GoogleGeminiParser')
OpenRouterParser = getattr(ai_mod, 'OpenRouterParser', None)

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

if OpenRouterParser:
    print('\n== Debug OpenRouterParser.parse (debug_only=True) ==')
    try:
        res2 = OpenRouterParser.parse(text=sample_text, api_key='DUMMY_KEY', model_name='google/gemini-2.0-flash-exp', debug_only=True)
        print(json.dumps(res2, indent=2, ensure_ascii=False))
    except Exception as e:
        print('OpenRouterParser error:', e)
else:
    print('OpenRouterParser not found in module')
