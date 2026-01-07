# -*- coding: utf-8 -*-
import logging
import re
import base64

_logger = logging.getLogger(__name__)


class TesseractOCRService:
    """
    Сервис для распознавания текста из изображений с помощью Tesseract OCR.
    Изолированный модуль для работы с OCR независимо от парсеров.
    """
    
    @staticmethod
    def is_available():
        """
        Проверка доступности Tesseract OCR.
        
        :return: bool - True если Tesseract доступен
        """
        try:
            import pytesseract
            from PIL import Image
            return True
        except ImportError:
            return False
    
    @staticmethod
    def preprocess_image(image):
        """
        Предобработка изображения для улучшения качества OCR.
        Оптимизирована для украинских документов.
        
        :param image: PIL Image
        :return: PIL Image (обработанное)
        """
        try:
            from PIL import ImageEnhance, ImageFilter
            
            # 1. Конвертировать в RGB если нужно
            if image.mode not in ['RGB', 'L']:
                image = image.convert('RGB')
            
            # 2. Увеличить разрешение для маленьких изображений
            # Tesseract работает лучше при 300+ DPI
            min_dimension = 2000
            if image.width < min_dimension or image.height < min_dimension:
                scale = max(min_dimension / image.width, min_dimension / image.height)
                new_size = (int(image.width * scale), int(image.height * scale))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                _logger.info(f"✅ Изображение увеличено до {new_size}")
            
            # 3. Конвертировать в grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # 4. Повысить контраст (важно для кириллицы)
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # 5. Резкость (умеренная - важно для кириллических букв)
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.3)
            
            # 6. Убрать шум медианным фильтром
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            _logger.info(f"✅ Предобработка: размер={image.size}, режим={image.mode}")
            
            return image
        except Exception as e:
            _logger.warning(f"⚠️ Ошибка предобработки изображения: {e}, используется оригинал")
            return image
    
    @staticmethod
    def extract_text_from_image(image_data, lang='ukr+eng', config='--psm 6', preprocess=True):
        """
        Извлечение текста из изображения с помощью Tesseract OCR.
        
        :param image_data: Бинарные данные изображения
        :param lang: Языки для распознавания (по умолчанию только украинский для лучшей точности)
        :param config: Конфигурация Tesseract (по умолчанию --psm 6 = uniform block of text)
        :param preprocess: Применять предобработку изображения для улучшения качества
        :return: dict с извлеченным текстом или ошибкой
        """
        try:
            import pytesseract
            from PIL import Image
            import io
            _logger.info("✅ Tesseract OCR импортирован успешно")
        except ImportError as e:
            _logger.error(f"❌ Ошибка импорта Tesseract: {e}")
            return {
                'success': False,
                'text': '',
                'error': f'Tesseract OCR не встановлений. Ошибка импорта: {e}\n\nВстановіть: sudo apt install tesseract-ocr tesseract-ocr-ukr && pip3 install pytesseract Pillow'
            }
        
        try:
            # Конвертировать binary в PIL Image
            image = Image.open(io.BytesIO(image_data))
            original_size = image.size
            original_mode = image.mode
            _logger.info(f"✅ Изображение открыто: {original_size}, {original_mode}")
            
            # Предобработка изображения для улучшения качества
            if preprocess:
                image = TesseractOCRService.preprocess_image(image)
                _logger.info(f"✅ Предобработка завершена: {image.size}, {image.mode}")
            
            # Распознать текст с улучшенной конфигурацией для украинского языка
            # PSM modes:
            # --psm 4 = Assume a single column of text of variable sizes
            # --psm 6 = Assume a single uniform block of text (лучше для документов)
            # --oem 1 = Neural nets LSTM only (лучшая точность)
            # 
            # Дополнительные параметры для украинского:
            # tessedit_char_whitelist - ограничить символы (но может пропустить специальные)
            enhanced_config = '--psm 6 --oem 1'
            
            # Если используется только украинский - добавить специфичные настройки
            if lang == 'ukr':
                # Для украинского документа - предпочитать кириллицу
                enhanced_config += ' -c preserve_interword_spaces=1'
            
            text = pytesseract.image_to_string(
                image,
                lang=lang,
                config=enhanced_config
            )
            
            _logger.info(f"✅ OCR распознал {len(text)} символов")
            
            return {
                'success': True,
                'text': text.strip(),
                'error': None,
                'stats': {
                    'char_count': len(text.strip()),
                    'line_count': len([l for l in text.split('\n') if l.strip()]),
                    'original_size': original_size,
                    'processed_size': image.size,
                    'original_mode': original_mode,
                    'processed_mode': image.mode,
                    'preprocessed': preprocess,
                }
            }
        except Exception as e:
            _logger.error(f"❌ Ошибка OCR: {e}", exc_info=True)
            return {
                'success': False,
                'text': '',
                'error': f'Помилка OCR: {str(e)}'
            }
    
    @staticmethod
    def extract_text_smart(image_data, preprocess=True):
        """
        Интеллектуальное распознавание - пробует несколько вариантов языков.
        Сначала только украинский, потом с русским и английским.
        
        :param image_data: Бинарные данные изображения
        :param preprocess: Применять предобработку
        :return: dict с лучшим результатом
        """
        # Попытка 1: Только украинский (самая высокая точность)
        result = TesseractOCRService.extract_text_from_image(
            image_data, 
            lang='ukr', 
            preprocess=preprocess
        )
        
        if result['success'] and len(result['text'].strip()) > 50:
            _logger.info(f"✅ Распознано с украинским: {len(result['text'])} символов")
            result['lang_used'] = 'ukr'
            return result
        
        # Попытка 2: Украинский + Русский (для смешанных документов)
        result2 = TesseractOCRService.extract_text_from_image(
            image_data,
            lang='ukr+rus',
            preprocess=preprocess
        )
        
        if result2['success'] and len(result2['text'].strip()) > len(result.get('text', '').strip()):
            _logger.info(f"✅ Распознано с укр+рус: {len(result2['text'])} символов")
            result2['lang_used'] = 'ukr+rus'
            return result2
        
        # Попытка 3: Все языки (на случай английских слов)
        result3 = TesseractOCRService.extract_text_from_image(
            image_data,
            lang='ukr+rus+eng',
            preprocess=preprocess
        )
        
        if result3['success']:
            _logger.info(f"✅ Распознано с укр+рус+англ: {len(result3['text'])} символов")
            result3['lang_used'] = 'ukr+rus+eng'
            return result3
        
        # Возвращаем первый результат если все остальные не сработали
        result['lang_used'] = 'ukr (fallback)'
        return result
    
    @staticmethod
    def extract_image_from_html(html_content):
        """
        Извлечение изображения из HTML контента.
        Поддерживает:
        - Base64 изображения в data URI
        - Ссылки на attachments Odoo (/web/image/ID)
        
        :param html_content: HTML контент
        :return: tuple (image_data, source_type) или (None, None)
        """
        if not html_content:
            return None, None
        
        # Вариант 1: Base64 изображение напрямую в HTML
        pattern_base64 = r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)'
        matches = re.findall(pattern_base64, html_content)
        
        if matches:
            try:
                image_data = base64.b64decode(matches[0])
                _logger.info(f"✅ Извлечено base64 изображение, размер: {len(image_data)} байт")
                return image_data, 'base64'
            except Exception as e:
                _logger.error(f"❌ Ошибка декодирования base64: {e}")
        
        # Вариант 2: Ссылка на attachment (возвращаем ID для последующей загрузки)
        pattern_attachment = r'/web/image/(\d+)'
        matches = re.findall(pattern_attachment, html_content)
        
        if matches:
            attachment_id = int(matches[0])
            _logger.info(f"✅ Найдена ссылка на attachment ID: {attachment_id}")
            return attachment_id, 'attachment'
        
        return None, None
    
    @staticmethod
    def extract_image_from_odoo_attachment(env, attachment_id):
        """
        Извлечение изображения из Odoo attachment.
        
        :param env: Odoo environment
        :param attachment_id: ID вложения
        :return: binary image data или None
        """
        try:
            attachment = env['ir.attachment'].browse(attachment_id)
            
            if not attachment.exists():
                _logger.warning(f"❌ Attachment {attachment_id} не найден")
                return None
            
            if not attachment.datas:
                _logger.warning(f"❌ Attachment {attachment_id} пустой")
                return None
            
            image_data = base64.b64decode(attachment.datas)
            _logger.info(f"✅ Извлечено изображение из attachment {attachment_id}, размер: {len(image_data)} байт")
            return image_data
            
        except Exception as e:
            _logger.error(f"❌ Ошибка чтения attachment {attachment_id}: {e}")
            return None
    
    @staticmethod
    def get_supported_languages():
        """
        Получить список поддерживаемых языков Tesseract.
        
        :return: list языков или []
        """
        try:
            import pytesseract
            langs = pytesseract.get_languages()
            return langs
        except:
            return []
    
    @staticmethod
    def get_version():
        """
        Получить версию Tesseract.
        
        :return: str версия или None
        """
        try:
            import pytesseract
            return pytesseract.get_tesseract_version()
        except:
            return None
