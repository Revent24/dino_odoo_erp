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
            
            # Додати response_format тільки для Groq з правильним синтаксисом
            if is_groq:
                request_data["response_format"] = {"type": "json_object"}
            
            # Відправити запит до API
            _logger.info(f"Sending request to {api_base_url} with model {model_name}")
            _logger.debug(f"Request headers: {headers}")
            _logger.debug(f"Request data keys: {request_data.keys()}")
            
            response = requests.post(
                url=api_base_url,
                headers=headers,
                json=request_data,
                timeout=120
            )
            
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

КРИТИЧНО ВАЖЛИВО:
- Якщо надано зображення - уважно прочитайте ВСЬ текст з документа
- Розпізнайте всі цифри, дати, назви товарів
- Поверніть ТІЛЬКИ валідний JSON
- БЕЗ додаткового тексту до або після JSON
- БЕЗ markdown форматування (```json)
- БЕЗ пояснень
- Всі спеціальні символи в рядках мають бути правильно екрановані
- Переноси рядків в значеннях замінюйте на пробіли

Якщо зображення нечітке або пусте - поверніть JSON з пустими полями."""

        # Підготувати частини запиту
        parts = [{"text": system_prompt}]
        
        _logger.info(f"📝 System prompt length: {len(system_prompt)} chars")
        
        if text:
            _logger.info(f"📄 Adding text input: {len(text)} chars")
            # Перевірка: якщо текст надто великий, попередити
            if len(text) > 50000:
                _logger.warning(f"⚠️ Text is very large ({len(text)} chars). This may cause timeout!")
            parts.append({"text": f"\n\nТекст документа:\n{text}"})
        
        if image_data:
            # Визначити MIME type
            mime_type = "image/jpeg"  # За замовчуванням
            
            if isinstance(image_data, bytes):
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
            
            total_text_length = 0
            for i, part in enumerate(parts):
                if 'text' in part:
                    text_len = len(part['text'])
                    total_text_length += text_len
                    _logger.info(f"  Part {i}: text ({text_len} chars)")
                elif 'inline_data' in part:
                    _logger.info(f"  Part {i}: image ({part['inline_data']['mime_type']}, {len(part['inline_data']['data'])} chars)")
            
            # Адаптивный таймаут в зависимости от размера данных
            if image_data:
                # Для изображений - минимум 3 минуты, добавляем время на каждый MB
                image_size_mb = len(image_base64) / (1024 * 1024)
                timeout_seconds = max(180, int(180 + image_size_mb * 30))
                _logger.info(f"Image mode: {image_size_mb:.2f}MB, timeout: {timeout_seconds}s")
            else:
                # Для текста - минимум 2 минуты, добавляем время на каждые 1000 символов
                base_timeout = 120
                text_factor = total_text_length / 1000 * 5  # 5 секунд на каждую 1000 символов
                timeout_seconds = max(base_timeout, int(base_timeout + text_factor))
                _logger.info(f"Text mode: {total_text_length} chars, timeout: {timeout_seconds}s")
            
            _logger.info(f"⏱️ Starting Gemini request with timeout {timeout_seconds}s...")
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
                error_msg = f"⏱️ Таймаут після {elapsed_time:.1f}с (ліміт {timeout_seconds}с). Google Gemini не встиг відповісти. Можливі причини:\n1) Великий обсяг тексту (ви надіслали {total_text_length:,} символів)\n2) Проблеми з Google API (перевантаження серверів)\n3) Повільне інтернет-з'єднання\n\nРішення: 1) Спробуйте коротший текст 2) Спробуйте іншу модель (наприклад Groq Llama) 3) Почекайте і повторіть"
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
                error_msg = f"API Error: {response.status_code} - {response.text}"
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
            
            # Очистити JSON від control characters
            # Замінити неекрановані переноси рядків та інші контрольні символи
            import re
            # Видалити control characters (коди 0-31 крім \t, \n, \r які повинні бути екрановані)
            json_text_cleaned = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', json_text)
            
            # Якщо JSON обернутий в ```json ... ```, витягти
            if '```json' in json_text_cleaned:
                json_text_cleaned = json_text_cleaned.split('```json')[1].split('```')[0].strip()
            elif '```' in json_text_cleaned:
                json_text_cleaned = json_text_cleaned.split('```')[1].split('```')[0].strip()
            
            _logger.info(f"Cleaned JSON length: {len(json_text_cleaned)}")
            
            # Парсинг JSON
            parsed_data = json.loads(json_text_cleaned)
            
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
