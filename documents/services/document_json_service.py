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
        :param raw_json_str: оригінальний JSON рядок від AI (для збереження в ocr_result_text)
        :return: dict з результатами обробки
        """
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
            # 0. Зберегти оригінальний JSON в поле ocr_result_text
            if raw_json_str:
                import json
                # Форматувати JSON для кращої читабельності
                try:
                    formatted_json = json.dumps(json.loads(raw_json_str), indent=2, ensure_ascii=False)
                    document.ocr_result_text = formatted_json
                except:
                    document.ocr_result_text = raw_json_str
            
            # 1. Обробка header: номер, дата та тип документа
            if json_data.get('header'):
                header_data = json_data['header']
                
                # Номер документа
                if header_data.get('doc_number'):
                    document.number = header_data['doc_number']
                    result['document_number'] = header_data['doc_number']
                
                # Дата документа
                if header_data.get('doc_date'):
                    document.date = header_data['doc_date']
                
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
            
            # 3. Обробка lines: створення специфікацій
            if json_data.get('lines'):
                line_result = DocumentJSONService._process_lines(
                    document,
                    json_data['lines']
                )
                result['created_lines'] = line_result['created']
                result['updated_lines'] = line_result['updated']
                result['errors'].extend(line_result['errors'])
            
            # 4. Обчислення ПДВ
            if json_data.get('lines'):
                DocumentJSONService._calculate_vat_rate(document, json_data['lines'])
            
            result['success'] = True
            
        except Exception as e:
            _logger.error(f"Error processing JSON: {e}", exc_info=True)
            result['errors'].append(f"Загальна помилка: {str(e)}")
        
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
        
        # Пошук партнера по ЄДРПОУ
        Partner = env['dino.partner']
        partner = Partner.search([('egrpou', '=', edrpou)], limit=1)
        
        if not partner:
            # Створити нового партнера
            partner_vals = {
                'name': supplier_data.get('name', f'Partner {edrpou}'),
                'egrpou': edrpou,
                'inn': supplier_data.get('ipn'),
                'address': supplier_data.get('address'),
                'phone': supplier_data.get('phone'),
            }
            partner = Partner.create(partner_vals)
            _logger.info(f"Created new partner: {partner.name}")
        else:
            # Оновити дані партнера
            partner_vals = {}
            if supplier_data.get('name') and supplier_data['name'] != partner.name:
                partner_vals['name'] = supplier_data['name']
            if supplier_data.get('inn') and not partner.inn:
                partner_vals['inn'] = supplier_data['ipn']
            if supplier_data.get('address') and not partner.address:
                partner_vals['address'] = supplier_data['address']
            if supplier_data.get('phone') and not partner.phone:
                partner_vals['phone'] = supplier_data['phone']
            
            if partner_vals:
                partner.write(partner_vals)
        
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
        if supplier_data.get('tax_system'):
            TaxSystem = env['dino.tax.system']
            tax_system = TaxSystem.search([
                ('name', '=ilike', supplier_data['tax_system'])
            ], limit=1)
            
            if not tax_system:
                tax_system = TaxSystem.create({
                    'name': supplier_data['tax_system'],
                })
            
            if tax_system:
                partner.write({'tax_system_id': tax_system.id})
        
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
            doc_type = DocumentType.create({
                'name': doc_type_name,
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
        Uom = document.env['uom.uom']
        
        for line_data in lines_data:
            try:
                # Знайти або створити одиницю виміру (точне співпадіння!)
                unit_name = line_data.get('unit')
                uom = None
                
                if unit_name:
                    # Спочатку точний пошук
                    uom = Uom.search([('name', '=', unit_name)], limit=1)
                    
                    # Якщо не знайдено - створити нову одиницю
                    if not uom:
                        try:
                            _logger.info(f"Creating new UOM: {unit_name}")
                            # Знайти категорію "Unit" як базову
                            uom_category = document.env.ref('uom.product_uom_categ_unit', raise_if_not_found=False)
                            if not uom_category:
                                # Знайти будь-яку категорію
                                uom_category = document.env['uom.category'].search([], limit=1)
                            
                            if not uom_category:
                                # Створити базову категорію, якщо немає жодної
                                _logger.info("Creating new UOM category: Unit")
                                uom_category = document.env['uom.category'].create({
                                    'name': 'Unit',
                                })
                            
                            _logger.info(f"Using UOM category: {uom_category.name} (id: {uom_category.id})")
                            
                            uom = Uom.create({
                                'name': unit_name,
                                'category_id': uom_category.id,
                                'uom_type': 'reference',
                                'rounding': 0.01,
                            })
                            _logger.info(f"✅ Created UOM: {uom.name} (id: {uom.id})")
                        except Exception as uom_error:
                            _logger.error(f"Failed to create UOM '{unit_name}': {uom_error}", exc_info=True)
                            # Використати штучну одиницю або пропустити
                            uom = document.env.ref('uom.product_uom_unit', raise_if_not_found=False)
                
                # Знайти або створити в довіднику партнера
                supplier_nomenclature = None
                if document.partner_id:
                    nomenclature_vals = {
                        'partner_id': document.partner_id.id,
                        'name': line_data['name'],
                    }
                    
                    if uom:
                        nomenclature_vals['uom_id'] = uom.id
                    
                    supplier_nomenclature = PartnerNomenclature.search([
                        ('partner_id', '=', document.partner_id.id),
                        ('name', '=', line_data['name'])
                    ], limit=1)
                    
                    if supplier_nomenclature:
                        if uom and not supplier_nomenclature.uom_id:
                            supplier_nomenclature.uom_id = uom
                    else:
                        supplier_nomenclature = PartnerNomenclature.create(nomenclature_vals)
                
                # Перевірити існуючий рядок
                existing_spec = Specification.search([
                    ('document_id', '=', document.id),
                    ('name', '=', line_data['name'])
                ], limit=1)
                
                # Підготувати значення
                spec_vals = {
                    'name': line_data['name'],
                    'quantity': line_data.get('quantity', 1.0),
                    'price_untaxed': line_data.get('price_unit', 0.0),
                    'price_tax': line_data.get('price_total', 0.0) / line_data.get('quantity', 1.0) if line_data.get('price_total') and line_data.get('quantity') else 0.0,
                }
                
                if supplier_nomenclature:
                    spec_vals['supplier_nomenclature_id'] = supplier_nomenclature.id
                    if supplier_nomenclature.nomenclature_id:
                        spec_vals['nomenclature_id'] = supplier_nomenclature.nomenclature_id.id
                
                if uom:
                    spec_vals['uom_id'] = uom.id
                
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
    
    @staticmethod
    def _calculate_vat_rate(document, lines_data):
        """
        Обчислення ставки ПДВ на основі рядків документа.
        
        :param document: запис dino.operation.document
        :param lines_data: list з даними про позиції
        """
        total_subtotal = 0.0
        total_with_tax = 0.0
        
        for line_data in lines_data:
            subtotal = line_data.get('price_subtotal') or 0.0
            total = line_data.get('price_total') or 0.0
            
            if subtotal is not None:
                total_subtotal += float(subtotal)
            if total is not None:
                total_with_tax += float(total)
        
        if total_subtotal > 0 and total_with_tax > total_subtotal:
            vat_rate = ((total_with_tax - total_subtotal) / total_subtotal) * 100
            document.vat_rate = round(vat_rate, 2)
            _logger.info(f"Calculated VAT rate: {vat_rate:.2f}%")
