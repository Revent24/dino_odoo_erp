# -*- coding: utf-8 -*-
"""
Document JSON Service - Обробка JSON даних від парсерів та запис в БД.

Приймає стандартизований JSON від AI/Regex парсерів та розносить дані по моделям Odoo.
"""
import logging

_logger = logging.getLogger(__name__)


class DocumentJSONService:
    """
    Сервіс для обробки JSON даних від парсерів та запису в базу даних.
    Приймає стандартизований JSON та розносить інформацію по моделях.
    """
    
    @staticmethod
    def process_parsed_json(document, json_data, raw_json_str=None):
        """
        Обробка розпізнаного JSON та запис даних в документ.
        
        :param document: запис dino.operation.document
        :param json_data: dict з даними від парсера {'document': {...}, 'supplier': {...}, 'lines': [...]}
        :param raw_json_str: оригінальний JSON рядок від AI (debug, optional)
        :return: dict з результатами обробки
        """
        import time
        start_process = time.time()
        
        result = {
            'success': False,
            'created_lines': 0,
            'updated_lines': 0,
            'errors': [],
            'partner_found': False,
            'document_number': None,
            'supplier_name': None,
        }
        
        try:
            # Note: storing raw JSON in document was removed (field deleted)
            
            # 1. Обробка header: номер, дата та тип документа
            if json_data.get('header'):
                header_data = json_data['header']
                
                # Номер документа
                if header_data.get('doc_number'):
                    document.number = header_data['doc_number']
                    result['document_number'] = header_data['doc_number']
                
                # Дата документа
                doc_date = header_data.get('doc_date')
                if doc_date and str(doc_date).lower() != 'null':
                    try:
                        document.date = doc_date
                    except Exception as e:
                        _logger.warning(f"Invalid date format '{doc_date}': {e}")
                
                # Тип документа - знайти або створити
                if header_data.get('doc_type'):
                    doc_type = DocumentJSONService._process_document_type(
                        document.env,
                        header_data['doc_type']
                    )
                    if doc_type:
                        document.document_type_id = doc_type
            
            # 2. Обробка supplier: знайти або створити контрагента (дані в header)
            if json_data.get('header'):
                partner_start = time.time()
                header_data = json_data['header']
                
                # Підготувати дані постачальника з header
                supplier_data = {
                    'name': header_data.get('vendor_name'),
                    'edrpou': header_data.get('vendor_edrpou'),
                    'ipn': header_data.get('vendor_ipn'),
                    'iban': header_data.get('vendor_iban'),
                    'bank': header_data.get('vendor_bank'),
                    'bank_city': header_data.get('vendor_bank_city'),
                    'mfo': header_data.get('vendor_mfo'),
                    'address': header_data.get('vendor_address'),
                    'phone': header_data.get('vendor_phone'),
                    'tax_system': header_data.get('tax_system'),
                    'tax_percent': header_data.get('tax_percent'),
                }
                
                result['supplier_name'] = supplier_data.get('name', 'Невідомий')
                
                partner = DocumentJSONService._process_supplier(
                    document.env,
                    supplier_data,
                    document.partner_id
                )
                
                if partner:
                    document.partner_id = partner
                    result['partner_found'] = True
                    _logger.info(f"Partner processed: {partner.name}")
                _logger.info(f"⏱️ Partner processing: {time.time() - partner_start:.2f}s")
            
            # 3. Обробка lines: створення специфікацій
            if json_data.get('lines'):
                lines_start = time.time()
                line_result = DocumentJSONService._process_lines(
                    document,
                    json_data['lines']
                )
                result['created_lines'] = line_result['created']
                result['updated_lines'] = line_result['updated']
                result['errors'].extend(line_result['errors'])
                _logger.info(f"⏱️ Lines processing ({len(json_data['lines'])}): {time.time() - lines_start:.2f}s")
            
            # VAT rate теперь берется автоматически из системы налогообложения контрагента
            # через метод _ensure_partner_tax_system() в документе
            
            result['success'] = True
            
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            _logger.error(f"Error processing JSON: {e}\n{tb_str}")
            result['errors'].append(f"Загальна помилка: {str(e)}")
            result['errors'].append(f"Traceback: {tb_str}")
            
        _logger.info(f"⏱️ Total JSON Processing: {time.time() - start_process:.2f}s")
        return result
    
    @staticmethod
    def _process_supplier(env, supplier_data, existing_partner=None):
        """
        Обробка інформації про контрагента.
        Пошук по ЄДРПОУ або створення нового.
        
        :param env: Odoo environment
        :param supplier_data: dict з даними про постачальника
        :param existing_partner: вже обраний партнер в документі
        :return: запис dino.partner
        """
        # Якщо партнер вже обраний - не змінюємо
        if existing_partner:
            return existing_partner
        
        edrpou = supplier_data.get('edrpou')
        if not edrpou:
            _logger.warning("No EDRPOU provided for supplier")
            return None
        
        # Пошук партнера по ЄДРПОУ (захист від дублювання)
        Partner = env['dino.partner']
        partner = Partner.search([('egrpou', '=', edrpou)], limit=1)
        
        if not partner:
            # Створити нового партнера
            # ПРІОРИТЕТ: Спочатку спробувати отримати дані з реєстру по ЄДРПОУ
            partner_vals = {'egrpou': edrpou}
            
            # 🔍 Спроба 1: API запит до реєстру
            registry_data = {}
            try:
                from odoo.addons.dino_erp.api_integration.services.partners_service import fetch_partner_registry_data
                _logger.info(f"🌐 Fetching registry data for EGRPOU: {edrpou}")
                registry_data = fetch_partner_registry_data(edrpou)
                
                if registry_data:
                    _logger.info(f"✅ Registry data received: {list(registry_data.keys())}")
                    partner_vals.update(registry_data)
                else:
                    _logger.warning(f"⚠️ No registry data for EGRPOU: {edrpou}")
            except Exception as e:
                _logger.warning(f"⚠️ Failed to fetch registry for {edrpou}: {e}")
            
            # 🔍 Спроба 2: Якщо не отримали name з реєстру - взяти з AI
            if 'name' not in partner_vals or not partner_vals['name']:
                ai_name = supplier_data.get('name')
                if ai_name:
                    # Записати назву з AI в ВСІ поля назви
                    partner_vals['name'] = ai_name
                    partner_vals['full_name'] = ai_name  # Повна назва = назва з AI
                    partner_vals['name_short'] = ai_name  # Коротка назва = назва з AI
                    _logger.info(f"📝 Using AI name (full + short): {ai_name}")
                else:
                    partner_vals['name'] = f'Partner {edrpou}'
                    _logger.warning(f"⚠️ No name from API or AI, using default: Partner {edrpou}")
            
            # Додати інші дані з AI (якщо не прийшли з реєстру)
            if supplier_data.get('ipn') and 'inn' not in partner_vals:
                partner_vals['inn'] = supplier_data['ipn']
            if supplier_data.get('address') and 'address' not in partner_vals:
                partner_vals['address'] = supplier_data['address']
            if supplier_data.get('phone') and 'phone' not in partner_vals:
                partner_vals['phone'] = supplier_data['phone']
            
            # ПЕРЕВІРКА: Останній пошук перед створенням (захист від race condition)
            existing = Partner.search([('egrpou', '=', edrpou)], limit=1)
            if existing:
                _logger.warning(f"⚠️ Partner with EGRPOU {edrpou} already exists (race condition), using existing")
                partner = existing
            else:
                partner = Partner.create(partner_vals)
                _logger.info(f"✅ Created new partner: {partner.name} (EGRPOU: {edrpou})")
        else:
            # Партнер знайдений по ЄДРПОУ - НЕ оновлюємо дані, беремо як є
            # (Користувач: "когда к-гент уже создан, обновлять его не нужно")
            _logger.info(f"✅ Partner found by EGRPOU {edrpou}: {partner.name}. Update skipped.")
        
        # Обробка банківського рахунку
        if supplier_data.get('iban'):
            BankAccount = env['dino.partner.bank.account']
            BankAccount.find_or_create(
                partner_id=partner.id,
                iban=supplier_data['iban'],
                bank_name=supplier_data.get('bank'),
                bank_city=supplier_data.get('bank_city'),
                bank_mfo=supplier_data.get('mfo')
            )
        
        # Обробка системи оподаткування
        TaxSystem = env['dino.tax.system']
        tax_system = None
        tax_percent = supplier_data.get('tax_percent')
        tax_system_name = supplier_data.get('tax_system')

        # 1. Пріоритет: Якщо відома ставка ПДВ -> Шукаємо існуючу систему з таким відсотком
        # Щоб не плодити дублі
        if tax_percent is not None:
            tax_system = TaxSystem.search([('vat_rate', '=', tax_percent)], limit=1)
        
        # 2. Якщо по ставці не знайшли (або ставки немає), але є назва -> Шукаємо по назві
        if not tax_system and tax_system_name:
            tax_system = TaxSystem.search([('name', '=ilike', tax_system_name)], limit=1)
            
        # 3. Якщо нічого не знайшли -> Створюємо
        if not tax_system:
            if tax_percent is not None:
                # Якщо ІІ не дав назву, формуємо стандартну "Загальна система..."
                if not tax_system_name:
                    rate_str = f"{int(tax_percent)}" if tax_percent % 1 == 0 else f"{tax_percent}"
                    new_name = f"Загальна система, платник ПДВ {rate_str}%"
                else:
                    new_name = tax_system_name
                
                tax_system = TaxSystem.create({
                    'name': new_name,
                    'vat_rate': tax_percent
                })
                _logger.info(f"Created new tax system '{new_name}' with rate {tax_percent}%")
            elif tax_system_name:
                # Тільки назва відома
                tax_system = TaxSystem.create({'name': tax_system_name})
                _logger.info(f"Created new tax system '{tax_system_name}'")

        # Прив'язати до партнера (якщо ще не прив'язано або це новий партнер)
        if tax_system and (not partner.tax_system_id or not existing_partner):
            partner.write({'tax_system_id': tax_system.id})
            _logger.info(f"Assigned tax system '{tax_system.name}' to partner '{partner.name}'")
        
        return partner
    
    @staticmethod
    def _process_document_type(env, doc_type_name):
        """
        Обробка типу документа: знайти або створити.
        
        :param env: Odoo environment
        :param doc_type_name: назва типу документа (напр. "Видаткова накладна")
        :return: запис dino.document.type або None
        """
        if not doc_type_name:
            return None
        
        DocumentType = env['dino.document.type']
        
        # Точний пошук
        doc_type = DocumentType.search([('name', '=', doc_type_name)], limit=1)
        
        if not doc_type:
            # Пошук через ilike (на випадок варіацій)
            doc_type = DocumentType.search([('name', '=ilike', doc_type_name)], limit=1)
        
        if not doc_type:
            # Створити новий тип
            _logger.info(f"Creating new document type: {doc_type_name}")
            # Генеруємо код з назви: перші літери кожного слова, верхній регістр
            code_parts = []
            for word in doc_type_name.split():
                if word:
                    code_parts.append(word[:3].upper())
            code = '_'.join(code_parts) if code_parts else doc_type_name[:10].upper()
            
            doc_type = DocumentType.create({
                'name': doc_type_name,
                'code': code,
            })
        
        return doc_type
    
    @staticmethod
    def _process_lines(document, lines_data):
        """
        Обробка рядків специфікації з JSON.
        
        :param document: запис dino.operation.document
        :param lines_data: list з даними про позиції
        :return: dict з результатами {'created': int, 'updated': int, 'errors': list}
        """
        result = {
            'created': 0,
            'updated': 0,
            'errors': []
        }
        
        PartnerNomenclature = document.env['dino.partner.nomenclature']
        Specification = document.env['dino.operation.document.specification']
        DinoUom = document.env['dino.uom']
        
        for line_data in lines_data:
            try:
                # Find or create unit of measure using dino.uom
                unit_name = line_data.get('unit')
                uom = None
                
                if unit_name:
                    # Use find_or_create method from dino.uom model
                    uom = DinoUom.find_or_create(unit_name)
                    if uom:
                        _logger.info(f"Using UOM: {uom.name} (id: {uom.id})")
                
                # Find or create in partner nomenclature
                supplier_nomenclature = None
                if document.partner_id:
                    supplier_nomenclature = PartnerNomenclature.find_or_create(
                        partner_id=document.partner_id.id,
                        supplier_name=line_data['name'],
                        auto_create=True,
                        uom_id=uom.id if uom else None
                    )
                
                # Перевірити існуючий рядок
                # ВАЖЛИВО: Шукаємо по sequence тільки якщо він НЕ дефолтний (10)
                existing_spec = None
                line_number = line_data.get('line_number', 0)
                
                if line_number > 0:
                    # Шукаємо рядок з таким же sequence (якщо він був заданий раніше)
                    existing_spec = Specification.search([
                        ('document_id', '=', document.id),
                        ('sequence', '=', line_number)
                    ], limit=1)
                    
                    if existing_spec:
                        _logger.info(f"✅ Found existing line by sequence={line_number}: {existing_spec.name}")
                
                if not existing_spec:
                    # Якщо не знайшли по sequence - шукаємо по name + sequence=10 (дефолтний)
                    # Це для оновлення старих рядків, які були створені без line_number
                    existing_spec = Specification.search([
                        ('document_id', '=', document.id),
                        ('name', '=', line_data['name']),
                        ('sequence', '=', 10)  # Тільки рядки з дефолтним sequence
                    ], limit=1)
                    
                    if existing_spec:
                        _logger.info(f"✅ Found existing line by name (default sequence): {existing_spec.name}")
                
                # Підготувати значення
                spec_vals = {
                    'name': line_data['name'],
                    'quantity': line_data.get('quantity', 1.0),
                    'price_untaxed': line_data.get('price_unit', 0.0),
                    'sequence': line_data.get('line_number', 0),
                }
                
                # Додати description якщо є
                if line_data.get('description'):
                    spec_vals['description'] = line_data['description']
                
                # Розрахунок price_tax (ціна за одиницю З ПДВ)
                # Пріоритет: price_unit_with_tax з AI, потім розрахунок
                if line_data.get('price_unit_with_tax'):
                    spec_vals['price_tax'] = line_data['price_unit_with_tax']
                else:
                    # Розрахувати з price_unit та tax_percent
                    price_unit = line_data.get('price_unit', 0.0)
                    tax_percent = line_data.get('tax_percent', 0)
                    if tax_percent > 0:
                        spec_vals['price_tax'] = price_unit * (1 + tax_percent / 100)
                    else:
                        spec_vals['price_tax'] = price_unit
                
                if supplier_nomenclature:
                    spec_vals['supplier_nomenclature_id'] = supplier_nomenclature.id
                    if supplier_nomenclature.nomenclature_id:
                        spec_vals['nomenclature_id'] = supplier_nomenclature.nomenclature_id.id
                
                if uom:
                    spec_vals['dino_uom_id'] = uom.id
                
                if existing_spec:
                    existing_spec.write(spec_vals)
                    result['updated'] += 1
                else:
                    spec_vals['document_id'] = document.id
                    Specification.create(spec_vals)
                    result['created'] += 1
                
            except Exception as e:
                _logger.error(f"Error processing line: {e}", exc_info=True)
                result['errors'].append(f"Рядок {line_data.get('line_number', '?')}: {str(e)}")
        
        return result
    
    # NOTE: VAT rate calculation removed
    # VAT rate теперь берется из системы налогообложения контрагента
    # через partner_id -> tax_system_id -> vat_rate
    # См. метод _ensure_partner_tax_system() в dino_document.py
