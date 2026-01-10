# -*- coding: utf-8 -*-
"""
AI Parser Service - Парсинг документів через AI моделі.

Підтримує:
- OpenAI-compatible API (OpenAI, OpenRouter, Azure OpenAI)
- Google Gemini API

Вхід: текст АБО зображення
Вихід: стандартизований JSON
"""
import re
import json
import logging
import requests
import base64
import os

_logger = logging.getLogger(__name__)


class AIParserService:
    """
    Фабрика AI парсерів.
    Маршрутизація на потрібний парсер залежно від типу агента.
    """
    
    @staticmethod
    def _load_parsing_template():
        """Загрузити шаблон парсингу з файлу"""
        try:
            template_path = os.path.join(
                os.path.dirname(__file__),
                'ai_parsing_template.md'
            )
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            _logger.error(f"Error loading parsing template: {e}")
            return "Поверни JSON з полями: header, lines, metadata"
    
    @staticmethod
    def _validate_and_fix_math(result):
        """
        Перевірити і виправити математику в результаті парсингу.
        
        НОВИЙ АЛГОРИТМ (2026-01-09):
        1. Розрахунок ставки ПДВ з підсумків документа (ОДНА для всього документа)
        2. Заповнення відсутніх полів у рядках (price_unit, price_subtotal, price_total)
        3. Округлення: 0.001 для розрахунків → 0.01 для запису
        4. Розподіл різниці округлення пропорційно (підсумок документа = ІСТИНА)
        5. Фінальна валідація
        
        :param result: dict з даними від AI
        :return: result з виправленою математикою + список попереджень
        """
        warnings = []
        
        try:
            header = result.get('header', {})
            lines = result.get('lines', [])
            
            if not lines:
                return result, warnings
            
            # ========================
            # ЕТАП 1: Розрахунок ставки ПДВ з підсумків документа
            # ========================
            tax_percent = 0.0
            
            amount_untaxed = header.get('amount_untaxed', 0)
            amount_tax = header.get('amount_tax', 0)
            amount_total = header.get('amount_total', 0)
            
            # Спосіб 1: З amount_tax та amount_untaxed
            if amount_untaxed and amount_tax:
                tax_percent = round((amount_tax / amount_untaxed) * 100, 2)
                _logger.info(f"📊 Ставка ПДВ розрахована з підсумків: {tax_percent}%")
            
            # Спосіб 2: З різниці amount_total - amount_untaxed
            elif amount_total and amount_untaxed:
                amount_tax = amount_total - amount_untaxed
                header['amount_tax'] = round(amount_tax, 2)
                tax_percent = round((amount_tax / amount_untaxed) * 100, 2)
                _logger.info(f"📊 Ставка ПДВ розрахована з різниці: {tax_percent}%")
                warnings.append(f"Header: Розраховано amount_tax = {amount_tax:.2f}")
            
            # Спосіб 3: Якщо немає підсумків, припустити стандартну ставку 20%
            elif amount_total and not amount_untaxed:
                tax_percent = 20.0
                amount_untaxed = round(amount_total / 1.20, 2)
                amount_tax = amount_total - amount_untaxed
                header['amount_untaxed'] = amount_untaxed
                header['amount_tax'] = amount_tax
                _logger.warning(f"⚠️ Підсумок БЕЗ ПДВ відсутній, припускаємо ставку 20%")
                warnings.append(f"Header: Припущено ставку ПДВ 20%, розраховано amount_untaxed = {amount_untaxed:.2f}")
            
            header['tax_percent'] = tax_percent
            
            # ========================
            # ЕТАП 2: Заповнення відсутніх полів у рядках
            # ========================
            for idx, line in enumerate(lines, 1):
                qty = line.get('quantity', 0)
                price_unit = line.get('price_unit')
                price_unit_with_tax = line.get('price_unit_with_tax')
                price_subtotal = line.get('price_subtotal')
                price_total = line.get('price_total')
                
                # Округлення: внутрішні розрахунки до 3 знаків, запис до 2
                
                # СЦЕНАРІЙ 1: Є price_unit БЕЗ ПДВ
                if price_unit and qty:
                    # Розрахувати price_subtotal
                    if not price_subtotal:
                        calc_subtotal = qty * price_unit
                        line['price_subtotal'] = round(calc_subtotal, 2)
                        warnings.append(f"Рядок {idx}: Розраховано price_subtotal = {line['price_subtotal']:.2f}")
                    
                    # Розрахувати price_unit_with_tax
                    if not price_unit_with_tax and tax_percent:
                        calc_price_with_tax = price_unit * (1 + tax_percent / 100)
                        line['price_unit_with_tax'] = round(calc_price_with_tax, 2)
                    
                    # Розрахувати price_total
                    if not price_total:
                        calc_total = line.get('price_subtotal', 0) * (1 + tax_percent / 100)
                        line['price_total'] = round(calc_total, 2)
                        warnings.append(f"Рядок {idx}: Розраховано price_total = {line['price_total']:.2f}")
                
                # СЦЕНАРІЙ 2: Є тільки price_unit_with_tax (З ПДВ)
                elif price_unit_with_tax and qty and not price_unit:
                    # Розрахувати price_unit БЕЗ ПДВ
                    if tax_percent:
                        calc_price_unit = price_unit_with_tax / (1 + tax_percent / 100)
                        line['price_unit'] = round(calc_price_unit, 2)
                        warnings.append(f"Рядок {idx}: Розраховано price_unit = {line['price_unit']:.2f}")
                    
                    # Розрахувати price_total
                    if not price_total:
                        calc_total = qty * price_unit_with_tax
                        line['price_total'] = round(calc_total, 2)
                        warnings.append(f"Рядок {idx}: Розраховано price_total = {line['price_total']:.2f}")
                    
                    # Розрахувати price_subtotal
                    if not price_subtotal and tax_percent:
                        calc_subtotal = line['price_total'] / (1 + tax_percent / 100)
                        line['price_subtotal'] = round(calc_subtotal, 2)
                        warnings.append(f"Рядок {idx}: Розраховано price_subtotal = {line['price_subtotal']:.2f}")
                
                # СЦЕНАРІЙ 3: Є тільки price_subtotal
                elif price_subtotal and qty and not price_unit:
                    # Зворотній розрахунок price_unit
                    calc_price_unit = price_subtotal / qty
                    line['price_unit'] = round(calc_price_unit, 2)
                    warnings.append(f"Рядок {idx}: Розраховано price_unit = {line['price_unit']:.2f} (зворотно)")
                    
                    # Розрахувати price_total
                    if not price_total:
                        calc_total = price_subtotal * (1 + tax_percent / 100)
                        line['price_total'] = round(calc_total, 2)
                        warnings.append(f"Рядок {idx}: Розраховано price_total = {line['price_total']:.2f}")
                
                # СЦЕНАРІЙ 4: Є тільки price_total
                elif price_total and qty and not price_subtotal:
                    # Розрахувати price_subtotal
                    if tax_percent:
                        calc_subtotal = price_total / (1 + tax_percent / 100)
                        line['price_subtotal'] = round(calc_subtotal, 2)
                        warnings.append(f"Рядок {idx}: Розраховано price_subtotal = {line['price_subtotal']:.2f}")
                    
                    # Розрахувати price_unit
                    if not price_unit and line.get('price_subtotal'):
                        calc_price_unit = line['price_subtotal'] / qty
                        line['price_unit'] = round(calc_price_unit, 2)
                        warnings.append(f"Рядок {idx}: Розраховано price_unit = {line['price_unit']:.2f}")
            
            # ========================
            # ЕТАП 3: Розподіл різниці округлення
            # ========================
            
            # Якщо підсумки не задані в header, порахувати їх
            if not amount_untaxed or not amount_total:
                amount_untaxed = sum(l.get('price_subtotal', 0) for l in lines)
                amount_total = sum(l.get('price_total', 0) for l in lines)
                header['amount_untaxed'] = round(amount_untaxed, 2)
                header['amount_total'] = round(amount_total, 2)
                header['amount_tax'] = round(amount_total - amount_untaxed, 2)
                warnings.append(f"Header: Розраховано підсумки з рядків")
                return result, warnings
            
            # Порахувати суму всіх рядків
            lines_subtotal = sum(l.get('price_subtotal', 0) for l in lines)
            lines_total = sum(l.get('price_total', 0) for l in lines)
            
            # Різниця між документом і сумою рядків
            difference_untaxed = amount_untaxed - lines_subtotal
            difference_total = amount_total - lines_total
            
            _logger.info(f"💰 Сума рядків: {lines_subtotal:.2f} (без ПДВ), {lines_total:.2f} (з ПДВ)")
            _logger.info(f"💰 Документ:     {amount_untaxed:.2f} (без ПДВ), {amount_total:.2f} (з ПДВ)")
            _logger.info(f"💰 Різниця:      {difference_untaxed:.2f} (без ПДВ), {difference_total:.2f} (з ПДВ)")
            
            # Якщо різниця більше 1 копійки → РОЗПОДІЛИТИ
            if abs(difference_untaxed) > 0.01:
                _logger.warning(f"⚠️ Різниця округлення: {difference_untaxed:.2f} грн → розподіляємо")
                warnings.append(f"🔄 Розподіл різниці округлення: {difference_untaxed:.2f} грн")
                
                # Розподілити пропорційно по рядках
                for idx, line in enumerate(lines, 1):
                    if lines_subtotal > 0:
                        weight = line.get('price_subtotal', 0) / lines_subtotal
                        adjustment = round(difference_untaxed * weight, 3)  # 3 знаки для точності
                        
                        old_subtotal = line.get('price_subtotal', 0)
                        new_subtotal = round(old_subtotal + adjustment, 2)
                        line['price_subtotal'] = new_subtotal
                        
                        # Перерахувати price_total
                        line['price_total'] = round(new_subtotal * (1 + tax_percent / 100), 2)
                        
                        if abs(adjustment) > 0.001:
                            warnings.append(f"  Рядок {idx}: {old_subtotal:.2f} → {new_subtotal:.2f} (коригування: {adjustment:+.3f})")
                
                # Остання перевірка (може залишитись 0.01 через округлення)
                final_subtotal = sum(l.get('price_subtotal', 0) for l in lines)
                final_diff = amount_untaxed - final_subtotal
                
                if abs(final_diff) >= 0.01:
                    # Додати/відняти останню копійку до найбільшого рядка
                    max_line = max(lines, key=lambda l: l.get('price_subtotal', 0))
                    max_line['price_subtotal'] = round(max_line['price_subtotal'] + final_diff, 2)
                    max_line['price_total'] = round(max_line['price_subtotal'] * (1 + tax_percent / 100), 2)
                    warnings.append(f"  📌 Остання копійка ({final_diff:+.2f}) додана до найбільшого рядка")
            
            # ========================
            # ЕТАП 4: Фінальна валідація
            # ========================
            final_untaxed = sum(l.get('price_subtotal', 0) for l in lines)
            final_total = sum(l.get('price_total', 0) for l in lines)
            
            # Гарантувати що суми співпадають
            diff_check = abs(final_untaxed - amount_untaxed)
            if diff_check > 0.01:
                _logger.error(f"❌ КРИТИЧНА ПОМИЛКА: Сума рядків ({final_untaxed:.2f}) не дорівнює підсумку ({amount_untaxed:.2f}), різниця: {diff_check:.2f}")
                warnings.append(f"❌ ПОМИЛКА: Не вдалось точно розподілити різницю! Залишок: {diff_check:.2f}")
            else:
                _logger.info(f"✅ Математична валідація успішна: {final_untaxed:.2f} === {amount_untaxed:.2f}")
            
            # Перевірка суми з ПДВ (можуть бути невеликі розбіжності через округлення кожного рядка)
            diff_total_check = abs(final_total - amount_total)
            if diff_total_check > 0.05:
                warnings.append(f"⚠️ Сума з ПДВ відрізняється на {diff_total_check:.2f} грн (допустимо до 0.05)")
        
        except Exception as e:
            warnings.append(f"❌ Помилка валідації математики: {e}")
            _logger.error(f"Math validation error: {e}", exc_info=True)
        
        return result, warnings
    
    @staticmethod
    def parse(text=None, image_data=None, agent_type='ai_openai_compatible', partner_name=None, **kwargs):
        """
        Парсинг тексту або зображення через AI.
        
        :param text: Текст документа (опціонально)
        :param image_data: Бінарні дані зображення (опціонально)
        :param agent_type: Тип AI агента
        :param partner_name: Назва партнера (опціонально)
        :param kwargs: Додаткові параметри (api_key, model_name, etc.)
        :return: dict з даними
        """
        if agent_type in ['ai_openai_compatible', 'ai_groq']:
            return OpenRouterParser.parse(text, image_data, partner_name, **kwargs)
        elif agent_type == 'ai_google':
            return GoogleGeminiParser.parse(text, image_data, partner_name, **kwargs)
        else:
            return {
                'success': False,
                'errors': [f'Unknown AI agent type: {agent_type}'],
                'document': {},
                'supplier': {},
                'lines': []
            }


class OpenRouterParser:
    """
    Парсер для OpenRouter API (підтримує всі моделі OpenRouter).
    Оптимізований для Gemini 2.0 Flash через OpenRouter.
    
    Вхід: текст АБО зображення
    Вихід: JSON
    """
    
    @staticmethod
    def parse(text=None, image_data=None, partner_name=None, **kwargs):
        """
        Парсинг через OpenRouter API.
        
        :param text: Текст документа (опціонально)
        :param image_data: Бінарні дані зображення (опціонально)
        :param partner_name: Назва партнера
        :param kwargs: api_key, model_name, temperature, max_tokens, debug_only
        :return: dict
        """
        result = {
            'success': False,
            'document': {},
            'supplier': {},
            'lines': [],  # Кожен line повинен мати 'barcodes': []
            'errors': [],
            'tokens_used': 0,
            'cost': 0.0,
            'barcodes': []  # Загальний список всіх штрихкодів з документа
        }
        
        # 🔍 DEBUG MODE: Тільки формування запиту без відправки
        debug_only = kwargs.get('debug_only', False)
        
        try:
            # Параметри API
            api_key = kwargs.get('api_key')
            api_base_url = kwargs.get('api_base_url') or 'https://openrouter.ai/api/v1/chat/completions'
            model_name = kwargs.get('model_name') or 'google/gemini-2.0-flash-exp:free'
            temperature = kwargs.get('temperature', 0.0)
            max_tokens = kwargs.get('max_tokens', 4000)
            
            if not api_key:
                result['errors'].append('API key не вказаний')
                return result
            
            if not text and not image_data:
                result['errors'].append('Потрібен текст або зображення')
                return result
            
            # Завантажити шаблон парсингу з файлу
            parsing_template = AIParserService._load_parsing_template()
            
            # Додати список одиниць виміру якщо передано
            units_str = ""
            units_list = kwargs.get('units_list', [])
            if units_list:
                # Обмежити до 20 одиниць для економії токенів
                units_display = units_list[:20]
                units_str = f"\n\n#Units template: {', '.join(units_display)}"
                if len(units_list) > 20:
                    units_str += f" (+{len(units_list)-20})"
            
            # Системний промпт - МІНІМАЛЬНА обгортка
            system_prompt = f"""{parsing_template}{units_str}"""
            
            # Підготувати запит
            # Перевірка чи це Groq API
            is_groq = 'groq.com' in api_base_url.lower()
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Додаткові заголовки тільки для OpenRouter
            if not is_groq:
                headers["HTTP-Referer"] = "https://odoo.local"
                headers["X-Title"] = "Dino ERP Document Parser"
            
            # Сформувати повідомлення користувача
            user_message_content = []
            
            if image_data:
                # Якщо є зображення - пріоритет зображенню
                user_message_content.append({
                    "type": "text",
                    "text": "Розпізнай документ на зображенні. Використовуй ТІЛЬКИ дані з цього зображення."
                })
                
                # Конвертувати в base64
                if isinstance(image_data, bytes):
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                else:
                    image_base64 = image_data
                
                user_message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                })
            elif text:
                # Якщо тільки текст
                user_message_content.append({
                    "type": "text",
                    "text": f"Розпізнай цей документ:\n\n{text}"
                })
            
            request_data = {
                "model": model_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_message_content if len(user_message_content) > 1 else user_message_content[0]["text"]
                    }
                ]
            }
            
            # 🔍 Зберегти інформацію про запит для діагностики (завжди)
            if len(user_message_content) > 1:
                # Якщо декілька частин (текст + зображення) - показуємо всі
                user_text = "\n".join([item.get("text", "[IMAGE]") for item in user_message_content])
            else:
                # Якщо одна частина - витягуємо текст
                user_text = user_message_content[0].get("text", "")
            full_request_text = f"{system_prompt}\n\n{user_text}"
            result['debug_info'] = {'full_request': full_request_text}
            
            # 🔍 DEBUG MODE: Якщо debug_only=True, повернути БЕЗ запиту
            if debug_only:
                result['success'] = True
                result['errors'] = ['DEBUG MODE']
                return result
            
            # Додати response_format тільки для Groq з правильним синтаксисом
            if is_groq:
                request_data["response_format"] = {"type": "json_object"}
            
            # Відправити запит до API
            _logger.info(f"Sending request to {api_base_url} with model {model_name}")
            _logger.debug(f"Request headers: {headers}")
            # _logger.debug(f"Request data keys: {request_data.keys()}")
            
            import time
            req_start = time.time()
            
            try:
                response = requests.post(
                    url=api_base_url,
                    headers=headers,
                    json=request_data,
                    timeout=120
                )
                _logger.info(f"⏱️ API Response time: {time.time() - req_start:.2f}s")
            except requests.exceptions.Timeout:
                 _logger.error(f"⏱️ API Timeout after {time.time() - req_start:.2f}s")
                 raise
            
            # Логування помилки якщо є
            if response.status_code != 200:
                _logger.error(f"API Error {response.status_code}: {response.text}")
            
            response.raise_for_status()
            response_data = response.json()
            
            # Витягти JSON з відповіді
            content = response_data['choices'][0]['message']['content']
            parsed_json = json.loads(content)
            
            # Зберегти оригінальний JSON
            result['raw_json'] = content
            
            # Повернути повний parsed JSON як є (з header, lines, metadata)
            result['header'] = parsed_json.get('header', {})
            result['lines'] = parsed_json.get('lines', [])
            result['metadata'] = parsed_json.get('metadata', {})
            
            # Перевірити і виправити математику (AI тільки витягує дані, Python перевіряє)
            math_start = time.time()
            result, math_warnings = AIParserService._validate_and_fix_math(result)
            _logger.info(f"⏱️ Math validation time: {time.time() - math_start:.2f}s")
            
            if math_warnings:
                _logger.info(f"📊 Math validation: {len(math_warnings)} adjustments")
                for warning in math_warnings:
                    _logger.debug(f"  {warning}")
                # Додати попередження в metadata
                if 'metadata' not in result:
                    result['metadata'] = {}
                result['metadata']['math_warnings'] = math_warnings
            
            # Статистика токенів
            if 'usage' in response_data:
                result['tokens_used'] = response_data['usage'].get('total_tokens', 0)
                
                # Розрахунок вартості (для Gemini 2.0 Flash через OpenRouter - FREE!)
                result['cost'] = 0.0
            
            result['success'] = True
            _logger.info(f"✅ Successfully parsed. Tokens: {result['tokens_used']}, Cost: ${result['cost']:.4f}")
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ API request error: {e}", exc_info=True)
            result['errors'].append(f"Помилка API: {str(e)}")
        except json.JSONDecodeError as e:
            _logger.error(f"❌ JSON decode error: {e}", exc_info=True)
            result['errors'].append(f"Помилка парсингу JSON: {str(e)}")
        except Exception as e:
            _logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            result['errors'].append(f"Непередбачена помилка: {str(e)}")
        
        return result


class GoogleGeminiParser:
    """
    Парсер для прямого Google Gemini API (НЕ через OpenRouter).
    Використовується якщо потрібна пряма інтеграція з Google.
    """
    
    @staticmethod
    def parse(text=None, image_data=None, partner_name=None, **kwargs):
        """
        Парсинг через Google Gemini API.
        
        :param text: Текст документа (опціонально)
        :param image_data: Зображення (опціонально)
        :param partner_name: Назва партнера
        :param kwargs: api_key, model_name, temperature, max_tokens, debug_only
        :return: dict
        """
        result = {
            'success': False,
            'document': {},
            'supplier': {},
            'lines': [],  # Кожен line повинен мати 'barcodes': []
            'errors': [],
            'tokens_used': 0,
            'cost': 0.0,
            'barcodes': []  # Загальний список всіх штрихкодів з документа
        }
        
        # 🔍 DEBUG MODE: Тільки формування запиту без відправки
        debug_only = kwargs.get('debug_only', False)
        
        # Отримати параметри
        api_key = kwargs.get('api_key')
        if not api_key:
            result['errors'].append('API key обов\'язковий для Google Gemini')
            return result
        
        if not text and not image_data:
            result['errors'].append('Потрібен текст або зображення')
            return result
        
        model_name = kwargs.get('model_name', 'gemini-2.0-flash-exp')
        
        # Завантажити шаблон парсингу з файлу
        parsing_template = AIParserService._load_parsing_template()
        
        # Додати список одиниць виміру якщо передано
        units_str = ""
        units_list = kwargs.get('units_list', [])
        if units_list:
            # Обмежити до 20 одиниць для економії токенів
            units_display = units_list[:20]
            units_str = f"\n\n#Units template: {'; '.join(units_display)}"
            if len(units_list) > 20:
                units_str += f" (+{len(units_list)-20})"
        
        # Системний промпт - МІНІМАЛЬНА обгортка
        system_prompt = f"""{parsing_template}{units_str}"""

        # Підготувати частини запиту
        if text:
            # Об'єднати system prompt + документ в один part
            full_prompt = f"{system_prompt}\n\n# DOCUMENT FOR PARSING:\n{text}"
            parts = [{"text": full_prompt}]
            _logger.info(f"📄 Full prompt with document: {len(full_prompt)} chars")
        else:
            parts = [{"text": system_prompt}]
            _logger.info(f"📝 System prompt only: {len(system_prompt)} chars")
        
        if image_data:
            # Визначити MIME type
            mime_type = "image/jpeg"  # За замовчуванням
            
            # ✅ ВАЖЛИВО: Визначити тип image_data
            _logger.info(f"🔍 Gemini: image_data type = {type(image_data).__name__}, length = {len(image_data)}")
            
            # Перевірити чи це вже base64 строка (з Odoo attachment) чи байти
            if isinstance(image_data, str):
                # Це вже base64 string від Odoo
                _logger.info(f"Image data is base64 string: {len(image_data)} chars")
                _logger.info(f"First 100 chars of base64: {image_data[:100]}")
                image_base64 = image_data
                # Спробувати визначити MIME type з початку декодованих даних
                try:
                    decoded_start = base64.b64decode(image_data[:100])
                    _logger.info(f"Decoded first bytes: {decoded_start[:20]}")
                    if decoded_start[:4] == b'\x89PNG':
                        mime_type = "image/png"
                        _logger.info("Detected PNG image")
                    elif decoded_start[:3] == b'\xff\xd8\xff':
                        mime_type = "image/jpeg"
                        _logger.info("Detected JPEG image")
                    elif decoded_start[:4] == b'RIFF' and len(decoded_start) > 12 and decoded_start[8:12] == b'WEBP':
                        mime_type = "image/webp"
                        _logger.info("Detected WEBP image")
                    else:
                        _logger.warning(f"Unknown image format, magic bytes: {decoded_start[:20].hex()}")
                except Exception as e:
                    _logger.error(f"Could not decode base64: {e}")
                    raise Exception(f"Invalid base64 image data: {e}")
            elif isinstance(image_data, bytes):
                # Оптимізувати розмір зображення якщо надто велике
                # Gemini підтримує до 20MB, але великі зображення обробляються довше
                max_size_mb = 5  # Обмежимо 5MB для швидкості
                if len(image_data) > max_size_mb * 1024 * 1024:
                    _logger.info(f"Image size {len(image_data)/1024/1024:.2f}MB > {max_size_mb}MB, resizing...")
                    try:
                        from PIL import Image
                        import io
                        
                        img = Image.open(io.BytesIO(image_data))
                        # Зменшити до максимум 2048px по найбільшій стороні
                        max_dimension = 2048
                        if max(img.size) > max_dimension:
                            ratio = max_dimension / max(img.size)
                            new_size = tuple(int(dim * ratio) for dim in img.size)
                            img = img.resize(new_size, Image.Resampling.LANCZOS)
                            _logger.info(f"Resized to {new_size}")
                        
                        # Конвертувати в JPEG для економії місця
                        output = io.BytesIO()
                        if img.mode in ('RGBA', 'LA', 'P'):
                            img = img.convert('RGB')
                        img.save(output, format='JPEG', quality=85, optimize=True)
                        image_data = output.getvalue()
                        mime_type = "image/jpeg"
                        _logger.info(f"Optimized image size: {len(image_data)/1024/1024:.2f}MB")
                    except ImportError:
                        _logger.warning("PIL not available, sending original image")
                    except Exception as e:
                        _logger.warning(f"Failed to optimize image: {e}, sending original")
                
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                # Визначити тип по magic bytes
                if image_data[:4] == b'\x89PNG':
                    mime_type = "image/png"
                elif image_data[:3] == b'\xff\xd8\xff':
                    mime_type = "image/jpeg"
                elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
                    mime_type = "image/webp"
            else:
                image_base64 = image_data
                # Спробувати визначити з початку base64
                try:
                    decoded_start = base64.b64decode(image_data[:20])
                    if decoded_start[:4] == b'\x89PNG':
                        mime_type = "image/png"
                    elif decoded_start[:3] == b'\xff\xd8\xff':
                        mime_type = "image/jpeg"
                except:
                    pass
            
            _logger.info(f"Image MIME type detected: {mime_type}, base64 length: {len(image_base64)}")
            
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": image_base64
                }
            })
        
        # Payload
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": kwargs.get('temperature', 0.0),
                "maxOutputTokens": kwargs.get('max_tokens', 4096)
            }
        }
        
        # 🔍 ДІАГНОСТИКА: Зберегти ПОВНИЙ текст запиту для аналізу (ЗАВЖДИ)
        full_request_parts = []
        for part in parts:
            if 'text' in part:
                full_request_parts.append(part['text'])
            elif 'inline_data' in part:
                full_request_parts.append(f"[IMAGE: {part['inline_data']['mime_type']}]")
        full_request_text = "\n\n".join(full_request_parts)
        result['debug_info'] = {'full_request': full_request_text}
        
        # 🔍 DEBUG MODE: Якщо debug_only=True, повернути тільки debug_info БЕЗ запиту
        if debug_only:
            _logger.warning("⚠️ DEBUG MODE: Запит НЕ відправлено, повертаю тільки debug_info")
            result['success'] = True
            result['errors'] = ['DEBUG MODE: Запит сформовано, але НЕ відправлено']
            return result
        
        try:
            # Если model_name уже содержит "models/", используем его как есть
            # Иначе добавляем префикс
            if model_name.startswith('models/'):
                full_model_path = model_name
            else:
                full_model_path = f"models/{model_name}"
            
            url = f"https://generativelanguage.googleapis.com/v1beta/{full_model_path}:generateContent?key={api_key}"
            
            _logger.info(f"Trying Gemini model: {full_model_path}")
            _logger.info(f"Gemini API URL: {url.replace(api_key, '***')}")
            _logger.info(f"Request parts count: {len(parts)}")
            
            # Підраховуємо ТІЛЬКИ текст документа (без системного промпту)
            document_text_length = len(text) if text else 0
            _logger.info(f"📄 Document text length: {document_text_length} chars")
            
            total_text_length = 0
            for i, part in enumerate(parts):
                if 'text' in part:
                    text_len = len(part['text'])
                    total_text_length += text_len
                    part_preview = part['text'][:50].replace('\n', ' ')
                    _logger.info(f"  Part {i}: text ({text_len} chars): {part_preview}...")
                elif 'inline_data' in part:
                    _logger.info(f"  Part {i}: image ({part['inline_data']['mime_type']}, {len(part['inline_data']['data'])} chars)")
            
            # Адаптивный таймаут в зависимости от размера данных
            if image_data:
                # Для изображений - от 60 до 120 секунд в зависимости от размера
                image_size_mb = len(image_base64) / (1024 * 1024)
                timeout_seconds = min(120, max(60, int(60 + image_size_mb * 20)))
                _logger.info(f"📷 Image mode: {image_size_mb:.2f}MB, timeout: {timeout_seconds}s")
            else:
                # Для текста - базовий таймаут 60с (було 30с, але Gemini може "думати" довше)
                base_timeout = 60
                # Використовуємо document_text_length замість total_text_length
                text_factor = min(60, document_text_length / 1000 * 3)  # 3 секунди на кожну 1000 символів, макс +60с
                timeout_seconds = int(base_timeout + text_factor)
                _logger.info(f"📝 Text mode: document={document_text_length} chars, total_request={total_text_length} chars, timeout: {timeout_seconds}s")
            
            _logger.info(f"⏱️ Starting Gemini request with timeout {timeout_seconds}s...")
            
            import time
            start_time = time.time()
            
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=timeout_seconds
                )
                elapsed_time = time.time() - start_time
                _logger.info(f"✅ Gemini responded in {elapsed_time:.2f}s")
            except requests.exceptions.Timeout:
                elapsed_time = time.time() - start_time
                error_msg = f"⏱️ Таймаут після {elapsed_time:.1f}с (ліміт {timeout_seconds}с).\n\nGoogle Gemini не встиг відповісти.\nДокумент: {document_text_length:,} символів\nПовний запит: {total_text_length:,} символів\n\n💡 Рекомендації:\n1. Перевірте з'єднання з інтернетом\n2. Спробуйте ще раз (можливо, сервер Google перевантажений)\n3. Використайте fallback агента (налаштуйте в Parser Agent)\n4. Спробуйте інший агент: Groq Llama або OpenRouter Gemini"
                _logger.error(error_msg)
                result['errors'].append(error_msg)
                return result
            except requests.exceptions.ConnectionError as e:
                error_msg = f"🌐 Помилка з'єднання з Gemini API. Перевірте інтернет: {str(e)}"
                _logger.error(error_msg)
                result['errors'].append(error_msg)
                return result
            
            _logger.info(f"Gemini response status: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text[:500]  # Обмежуємо довжину тексту помилки
                error_msg = f"❌ Google Gemini API Error {response.status_code}\n\n{error_text}\n\n💡 Можливі причини:\n• Неправильний API ключ\n• Вичерпано ліміт запитів (15 req/min або 1500 req/day)\n• Модель '{model_name}' недоступна\n• Проблеми з Google API\n\nПеревірте: Settings → API Keys → Google Gemini"
                _logger.error(error_msg)
                result['errors'].append(error_msg)
                return result
            
            response_data = response.json()
            
            # Логування відповіді
            _logger.info(f"Response has candidates: {'candidates' in response_data}")
            if 'candidates' in response_data:
                _logger.info(f"Candidates count: {len(response_data['candidates'])}")
            
            # Витягти JSON
            if 'candidates' not in response_data:
                _logger.error(f"No candidates in response. Response keys: {response_data.keys()}")
                result['errors'].append('Немає candidates у відповіді')
                return result
            
            candidate = response_data['candidates'][0]
            json_text = candidate['content']['parts'][0].get('text', '')
            
            _logger.info(f"Extracted JSON length: {len(json_text)} chars")
            _logger.debug(f"Raw JSON preview: {json_text[:200]}...")
            
            # Зберегти оригінальний JSON
            result['raw_json'] = json_text
            
            # Очистити JSON від control characters та витягти з markdown
            import re
            
            # СПОЧАТКУ витягти JSON з markdown (якщо є) - дозволяємо моделі використовувати природний стиль
            json_text_cleaned = json_text
            if '```json' in json_text_cleaned:
                # Витягти між ```json та наступним ```
                match = re.search(r'```json\s*(.+?)\s*```', json_text_cleaned, re.DOTALL)
                if match:
                    json_text_cleaned = match.group(1).strip()
            elif '```' in json_text_cleaned:
                # Витягти між будь-якими ``` та ```
                match = re.search(r'```\s*(.+?)\s*```', json_text_cleaned, re.DOTALL)
                if match:
                    json_text_cleaned = match.group(1).strip()
            
            # ПОТІМ очистити control characters
            # Видалити control characters (коди 0-31 крім \t, \n, \r які повинні бути екрановані)
            json_text_cleaned = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', json_text_cleaned)
            
            _logger.info(f"Cleaned JSON length: {len(json_text_cleaned)}")
            
            # Парсинг JSON
            parsed_data = json.loads(json_text_cleaned)
            
            # Повернути повний parsed JSON як є
            result['header'] = parsed_data.get('header', {})
            result['lines'] = parsed_data.get('lines', [])
            result['metadata'] = parsed_data.get('metadata', {})
            
            # Перевірити і виправити математику (AI тільки витягує дані, Python перевіряє)
            math_start = time.time()
            result, math_warnings = AIParserService._validate_and_fix_math(result)
            _logger.info(f"⏱️ Gemini Math validation time: {time.time() - math_start:.2f}s")
            
            if math_warnings:
                _logger.info(f"📊 Math validation: {len(math_warnings)} adjustments")
                for warning in math_warnings:
                    _logger.debug(f"  {warning}")
                # Додати попередження в metadata
                if 'metadata' not in result:
                    result['metadata'] = {}
                result['metadata']['math_warnings'] = math_warnings
            
            result['success'] = True
            
            # Токени
            if 'usageMetadata' in response_data:
                metadata = response_data['usageMetadata']
                result['tokens_used'] = metadata.get('totalTokenCount', 0)
                
                # Вартість Gemini 2.0 Flash
                input_tokens = metadata.get('promptTokenCount', 0)
                output_tokens = metadata.get('candidatesTokenCount', 0)
                result['cost'] = (input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000
            
            _logger.info(f"✅ Successfully parsed with Gemini")
            
        except requests.RequestException as e:
            _logger.error(f"❌ Gemini API error: {e}")
            result['errors'].append(f"Помилка API: {str(e)}")
        except json.JSONDecodeError as e:
            _logger.error(f"❌ JSON parse error: {e}")
            result['errors'].append(f"Помилка JSON: {str(e)}")
        except Exception as e:
            _logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            result['errors'].append(f"Помилка: {str(e)}")
        
        return result
