#
#  -*- File: documents/services/regex_parser_service.py -*-
#
# -*- coding: utf-8 -*-
"""
Regex Parser Service - Парсинг документів через регулярні вирази.

Вхід: текст
Вихід: JSON
"""
import re
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class RegexParserService:
    """
    Універсальний парсер на основі регулярних виразів.
    Витягує дані з різних форматів накладних/рахунків.
    
    ⚠️ Обмеження: не розуміє контекст, працює тільки з чітко структурованим текстом.
    Для складних документів краще використовувати AI парсери.
    """
    
    @staticmethod
    def parse(text, partner_name=None):
        """
        Парсинг тексту документа.
        
        :param text: Текст документа
        :param partner_name: Назва партнера (опціонально)
        :return: dict з даними
        """
        result = {
            'success': False,
            'document': {},
            'supplier': {},
            'lines': [],
            'errors': []
        }
        
        try:
            # 1. Нормалізація тексту
            text = RegexParserService._normalize_text(text)
            
            # 2. Витягти номер і дату документа
            doc_info = RegexParserService._extract_document_info(text)
            result['document'] = doc_info
            
            # 3. Витягти інформацію про постачальника
            supplier_info = RegexParserService._extract_supplier_info(text)
            result['supplier'] = supplier_info
            
            # 4. Витягти табличну частину
            lines = RegexParserService._extract_lines(text)
            result['lines'] = lines
            
            result['success'] = True if lines else False
            
            if not lines:
                result['errors'].append('Не вдалося знайти табличну частину')
            
        except Exception as e:
            _logger.error(f"Error parsing text: {e}", exc_info=True)
            result['errors'].append(str(e))
        
        return result
    
    @staticmethod
    def _normalize_text(text):
        """Нормалізація тексту перед парсингом"""
        if not text:
            return text
        
        # Очистка HTML тегів
        text = re.sub(r'</p>|<br\s*/?>|</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        
        # Декодувати HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        text = text.replace('&quot;', '"')
        
        # Замінити табуляції на пробіли
        text = text.replace('\t', ' ')
        
        # Множинні пробіли → один
        text = re.sub(r' {2,}', ' ', text)
        
        # Пробіли на початку/кінці рядків
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        # Множинні переноси рядків
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Неразривні пробіли
        text = re.sub(r'[\u00A0\u2000-\u200B\u202F\u205F\u3000]', ' ', text)
        
        # BOM і невидимі символи
        text = text.replace('\ufeff', '')
        text = text.replace('\u200b', '')
        
        return text.strip()
    
    @staticmethod
    def _extract_document_info(text):
        """Витягнути номер і дату документа"""
        doc_info = {'number': None, 'date': None}
        
        # Паттерни для номера
        number_patterns = [
            r'[РР]ахунок[- ]?фактура[\s№#]+([А-ЯІЄЇA-Z\d\-]+)\s+від',
            r'Видаткова накладна[\s№#]+(\d+)',
            r'РАХУНОК[- ]?ФАКТУРА[\s№#]+([А-ЯІЄЇA-Z\d\-]+)',
            r'[РР]ахунок на оплату[\s№#]+([А-ЯІЄЇA-Z\d\-]+)',
            r'№\s*([А-ЯІЄЇA-Z\d\-]+)\s+від',
        ]
        
        for pattern in number_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
            if match:
                doc_info['number'] = match.group(1).strip()
                break
        
        # Паттерни для дати
        date_patterns = [
            r'від\s+(\d{1,2})\s+([А-ЯІЄЇа-яієї]+)\s+(\d{4})',
            r'(\d{1,2})\s+([А-ЯІЄЇа-яієї]+)\s+(\d{4})\s*р',
            r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
            if match:
                date_str = match.group(0).strip()
                parsed_date = RegexParserService._parse_ukrainian_date(date_str)
                if parsed_date:
                    doc_info['date'] = parsed_date
                break
        
        return doc_info
    
    @staticmethod
    def _parse_ukrainian_date(date_str):
        """Перетворення української дати в datetime"""
        months_uk = {
            'січня': 1, 'січень': 1,
            'лютого': 2, 'лютий': 2,
            'березня': 3, 'березень': 3,
            'квітня': 4, 'квітень': 4,
            'травня': 5, 'травень': 5,
            'червня': 6, 'червень': 6,
            'липня': 7, 'липень': 7,
            'серпня': 8, 'серпень': 8,
            'вересня': 9, 'вересень': 9,
            'жовтня': 10, 'жовтень': 10,
            'листопада': 11, 'листопад': 11,
            'грудня': 12, 'грудень': 12,
        }
        
        try:
            # Формат: "31 Грудня 2024"
            match = re.search(r'(\d{1,2})\s+([А-ЯІЄЇа-яієї]+)\s+(\d{4})', date_str, re.IGNORECASE)
            if match:
                day = int(match.group(1))
                month_name = match.group(2).lower().strip()
                year = int(match.group(3))
                
                month = months_uk.get(month_name)
                if month:
                    return datetime(year, month, day).date()
            
            # Формат: "31.12.2024"
            match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', date_str)
            if match:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                
                if year < 100:
                    year += 2000
                
                return datetime(year, month, day).date()
        
        except (ValueError, AttributeError) as e:
            _logger.warning(f"Error parsing date '{date_str}': {e}")
        
        return None
    
    @staticmethod
    def _extract_supplier_info(text):
        """Витягти інформацію про постачальника"""
        supplier_info = {
            'name': None,
            'edrpou': None,
            'ipn': None,
            'phone': None,
            'iban': None,
            'bank': None,
            'address': None
        }
        
        # ЄДРПОУ
        edrpou_match = re.search(r'ЄДРПОУ[:\s]+(\d{8,10})', text, re.IGNORECASE)
        if edrpou_match:
            supplier_info['edrpou'] = edrpou_match.group(1)
        
        # ІПН
        ipn_match = re.search(r'ІПН[:\s]+(\d+)', text, re.IGNORECASE)
        if ipn_match:
            supplier_info['ipn'] = ipn_match.group(1)
        
        # IBAN
        iban_match = re.search(r'[РрPp]/[рp][:\s]+(UA\d+)', text, re.IGNORECASE)
        if iban_match:
            supplier_info['iban'] = iban_match.group(1)
        
        # Телефон
        phone_match = re.search(r'тел[\.:\s]+(\+?\d[\d\s\(\)\-]+)', text, re.IGNORECASE)
        if phone_match:
            supplier_info['phone'] = phone_match.group(1).strip()
        
        # Назва постачальника
        name_patterns = [
            r'Постачальник[:\s]+(.*?)(?=\n|\r|ЄДРПОУ|ІПН)',
            r'Продавець[:\s]+(.*?)(?=\n|\r|ЄДРПОУ|ІПН)',
        ]
        
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if name_match:
                name = name_match.group(1).strip()
                name = re.sub(r'\s+', ' ', name)
                supplier_info['name'] = name
                break
        
        return supplier_info
    
    @staticmethod
    def _extract_lines(text):
        """Витягти табличну частину"""
        lines = []
        
        # Знайти початок таблиці
        table_start_patterns = [
            r'№\s+Товар.*?Ціна.*?Сума',
            r'№\s+Код.*?Номенклатура.*?Кількість',
            r'Договір[:\s]',
        ]
        
        table_start_match = None
        for pattern in table_start_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                table_start_match = match
                break
        
        if not table_start_match:
            _logger.warning("Could not find table start")
            return lines
        
        # Текст після початку таблиці
        table_text = text[table_start_match.end():]
        
        # Знайти кінець таблиці
        table_end_patterns = [
            r'(?:Разом|Всього|Усього|Найменувань)[:\s]',
            r'Всього на суму',
        ]
        
        table_end_pos = len(table_text)
        for pattern in table_end_patterns:
            match = re.search(pattern, table_text, re.IGNORECASE)
            if match:
                table_end_pos = match.start()
                break
        
        table_text = table_text[:table_end_pos]
        
        # Парсинг рядків таблиці
        # Паттерн: №, назва, кількість, од, ціна, сума
        line_pattern = r'[№#]?\s*(\d+)\s+(.+?)\s+(\d+[\d\s,\.]*)\s+(шт\.?|од\.?|грн\.?|м\.?п?\.?|кг\.?|л\.?)\s+([\d\s,\.]+)\s+([\d\s,\.]+)'
        
        matches = list(re.finditer(line_pattern, table_text, re.IGNORECASE | re.MULTILINE))
        
        for match in matches:
            line_num = match.group(1)
            name = match.group(2).strip()
            quantity_str = match.group(3).replace(',', '.').replace(' ', '')
            uom = match.group(4).strip()
            price_str = match.group(5).replace(',', '.').replace(' ', '')
            subtotal_str = match.group(6).replace(',', '.').replace(' ', '')
            
            # Очистити назву
            name = re.sub(r'\s+', ' ', name)
            
            # Нормалізувати од. виміру
            uom_normalized, uom_coefficient = RegexParserService._normalize_uom(uom)
            
            try:
                quantity = float(quantity_str) * uom_coefficient
                price_unit = float(price_str) / uom_coefficient if uom_coefficient > 1 else float(price_str)
                subtotal = float(subtotal_str)
                
                lines.append({
                    'line_number': int(line_num),
                    'name': name,
                    'uom': uom_normalized,
                    'quantity': quantity,
                    'price_unit': price_unit,
                    'price_subtotal': subtotal,
                    'price_total': None,
                    'article': None,
                    'uktzed': None,
                    'note': None,
                })
            except (ValueError, ZeroDivisionError) as e:
                _logger.warning(f"Error parsing line {line_num}: {e}")
                continue
        
        return lines
    
    @staticmethod
    def _normalize_uom(uom_text):
        """Нормалізація одиниць виміру"""
        uom_text = uom_text.strip().lower()
        
        # Упаковки (100 шт)
        package_match = re.match(r'(\d+)\s*шт', uom_text)
        if package_match:
            coefficient = int(package_match.group(1))
            return ('шт', coefficient)
        
        # Базові одиниці
        uom_mapping = {
            'шт': ('шт', 1),
            'шт.': ('шт', 1),
            'од': ('шт', 1),
            'од.': ('шт', 1),
            'м': ('м', 1),
            'м.': ('м', 1),
            'м.п.': ('м', 1),
            'кг': ('кг', 1),
            'кг.': ('кг', 1),
            'л': ('л', 1),
            'л.': ('л', 1),
            'грн': ('шт', 1),
            'грн.': ('шт', 1),
        }
        
        return uom_mapping.get(uom_text, (uom_text, 1))
# End of file documents/services/regex_parser_service.py
