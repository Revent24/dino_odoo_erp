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
        if agent_type == 'ai_openai_compatible':
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
        :param kwargs: api_key, model_name, temperature, max_tokens
        :return: dict
        """
        result = {
            'success': False,
            'document': {},
            'supplier': {},
            'lines': [],
            'errors': [],
            'tokens_used': 0,
            'cost': 0.0,
        }
        
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
            
            # Завантажити шаблон парсингу
            parsing_template = AIParserService._load_parsing_template()
            
            # Системний промпт
            system_prompt = f"""Ти - експерт з розпізнавання українських бухгалтерських документів.
Твоє завдання: витягти дані ТІЛЬКИ з наданого документа і повернути строгий JSON.

⚠️ КРИТИЧНО ВАЖЛИВО:
- НЕ ВИГАДУЙ дані - якщо інформації немає в документі, повертай null
- Використовуй ТІЛЬКИ ті дані, які бачиш на зображенні/в тексті
- НЕ підставляй дані з пам'яті або з попередніх документів
- Якщо сумніваєшся - краще повернути null

{parsing_template}

Поверни ТІЛЬКИ JSON, без додаткового тексту."""
            
            # Підготувати запит
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://odoo.local",  # OpenRouter вимагає
                "X-Title": "Dino ERP Document Parser"
            }
            
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
                "response_format": {"type": "json_object"},
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
            
            # Відправити запит до API
            _logger.info(f"Sending request to {api_base_url} with model {model_name}")
            response = requests.post(
                url=api_base_url,
                headers=headers,
                json=request_data,
                timeout=120
            )
            
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
        :param kwargs: api_key, model_name, temperature, max_tokens
        :return: dict
        """
        result = {
            'success': False,
            'document': {},
            'supplier': {},
            'lines': [],
            'errors': [],
            'tokens_used': 0,
            'cost': 0.0
        }
        
        # Отримати параметри
        api_key = kwargs.get('api_key')
        if not api_key:
            result['errors'].append('API key обов\'язковий для Google Gemini')
            return result
        
        if not text and not image_data:
            result['errors'].append('Потрібен текст або зображення')
            return result
        
        model_name = kwargs.get('model_name', 'gemini-2.0-flash-exp')
        
        # Завантажити шаблон парсингу
        parsing_template = AIParserService._load_parsing_template()
        
        # Системний промпт
        system_prompt = f"""Ви - експерт з розпізнавання українських бухгалтерських документів.

{parsing_template}

Поверніть ТІЛЬКИ JSON без додаткового тексту."""

        # Підготувати частини запиту
        parts = [{"text": system_prompt}]
        
        if text:
            parts.append({"text": f"\n\nТекст документа:\n{text}"})
        
        if image_data:
            if isinstance(image_data, bytes):
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            else:
                image_base64 = image_data
            
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
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
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            
            _logger.info(f"Trying Gemini model: {model_name}")
            
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=60
            )
            
            if response.status_code != 200:
                error_msg = f"API Error: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                result['errors'].append(error_msg)
                return result
            
            response_data = response.json()
            
            # Витягти JSON
            if 'candidates' not in response_data:
                result['errors'].append('Немає candidates у відповіді')
                return result
            
            candidate = response_data['candidates'][0]
            json_text = candidate['content']['parts'][0].get('text', '')
            
            # Зберегти оригінальний JSON
            result['raw_json'] = json_text
            
            # Парсинг JSON
            parsed_data = json.loads(json_text)
            
            # Повернути повний parsed JSON як є
            result['header'] = parsed_data.get('header', {})
            result['lines'] = parsed_data.get('lines', [])
            result['metadata'] = parsed_data.get('metadata', {})
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
