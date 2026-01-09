# --- МОДЕЛЬ: Project Document (dino.operation.document)
# --- ФАЙЛ: models/dino_operation_document.py

from odoo import fields, models, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class DinoOperationDocument(models.Model):
    _name = 'dino.operation.document'
    _description = 'Project Document'
    _order = 'sequence, id'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mixin.auto.translate']
    _rec_name = 'number'
    
    # Отключить автоматический поиск партнёров для chatter
    # (используем dino.partner вместо res.partner)
    def _message_get_suggested_recipients(self, **kwargs):
        """Override to prevent looking for res.partner when using dino.partner"""
        recipients = self._message_get_suggested_recipients_batch(**kwargs)
        return recipients.get(self.id, {})
    
    def _message_get_suggested_recipients_batch(self, forced_emails=None, **kwargs):
        """Override to return empty suggestions (we use dino.partner, not res.partner)"""
        return {record.id: {} for record in self}

    project_id = fields.Many2one(
        'dino.project',
        string='Project',
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Manual ordering inside operation documents'
    )
    
    # Статус документа
    state = fields.Selection([
        ('draft', 'Draft'),
        ('edit', 'Edit'),
        ('ready', 'Ready'),
        ('done', 'Done'),
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Тип документа (новое поле)
    document_type_id = fields.Many2one(
        'dino.document.type',
        string='Document Type',
        required=True,
        default=lambda self: self.env.ref('dino_erp.document_type_other', raise_if_not_found=False),
        tracking=True,
        help='Type of document (invoice, bill, act, etc.)'
    )
    
    # Старое поле (deprecated)
    document_type = fields.Selection(
        selection=[
            ('quotation', 'Quotation'),
            ('order', 'Order'),
            ('invoice', 'Invoice'),
            ('waybill', 'Waybill'),
            ('payment_order', 'Payment Order'),
            ('other', 'Other'),
        ],
        string='Type (Old)'
    )
    number = fields.Char(
        string='Number'
    )
    date = fields.Date(
        string='Date',
        default=fields.Date.context_today
    )
    partner_id = fields.Many2one(
        'dino.partner',
        string='Partner'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    amount_untaxed = fields.Monetary(
        string='Subtotal',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    vat_rate = fields.Float(
        string='VAT Rate (%)',
        compute='_compute_vat_rate',
        store=False,  # Changed from True to False - always compute dynamically
        readonly=True
    )
    amount_tax = fields.Monetary(
        string='Tax',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )
    notes = fields.Html(
        string='Notes',
        translate=True
    )
    specification_ids = fields.One2many(
        'dino.operation.document.specification',
        'document_id',
        string='Specification',
        copy=True
    )
    attachment_ids = fields.One2many(
        'dino.document.attachment',
        'document_id',
        string='Attachments for Import'
    )
    
    # Поля для текстового импорта
    parser_agent_id = fields.Many2one(
        'dino.parser.agent',
        string='Parser Agent',
        help='Select parser agent for text import',
        default=lambda self: self.env['dino.parser.agent'].search([('is_default', '=', True)], limit=1)
    )
    import_text_content = fields.Html(
        string='Document Text',
        help='Paste document text here for parsing',
        sanitize=False  # Allow images and complex HTML
    )
    import_image = fields.Binary(
        string='Document Image/Screenshot',
        help='Upload document screenshot or photo for parsing'
    )
    import_image_filename = fields.Char('Image Filename')
    
    # Результат парсинга в JSON
    ocr_result_text = fields.Text(
        string='JSON Response',
        help='JSON response from AI parser (for debugging)',
        readonly=True
    )

    @api.depends('specification_ids.amount_untaxed', 'specification_ids.amount_tax')
    def _compute_amounts(self):
        for record in self:
            record.amount_untaxed = sum(record.specification_ids.mapped('amount_untaxed'))
            record.amount_tax = sum(record.specification_ids.mapped('amount_tax'))
            record.amount_total = record.amount_untaxed + record.amount_tax

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Автозаполнение полей из проекта при выборе"""
        if self.project_id:
            # Заполняем партнёра из `project.partner_id` (если задан)
            if self.project_id.partner_id:
                self.partner_id = self.project_id.partner_id
            # Если у проекта есть ставка НДС (derived from partner), обновим её
            if self.project_id.partner_id and self.project_id.partner_id.tax_system_id and self.project_id.partner_id.tax_system_id.vat_rate is not None:
                self.vat_rate = self.project_id.partner_id.tax_system_id.vat_rate
            # Проект не содержит валюту по умолчанию — оставляем её как есть

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Если пользователь изменил партнёра в документе вручную, обновляем ставку НДС"""
        for rec in self:
            if rec.partner_id and rec.partner_id.tax_system_id and rec.partner_id.tax_system_id.vat_rate is not None:
                rec.vat_rate = rec.partner_id.tax_system_id.vat_rate
            else:
                rec.vat_rate = 0.0

    def _compute_vat_rate(self):
        """Compute VAT rate from linked partner -> tax system"""
        for rec in self:
            if rec.partner_id and rec.partner_id.tax_system_id and rec.partner_id.tax_system_id.vat_rate is not None:
                rec.vat_rate = rec.partner_id.tax_system_id.vat_rate
            elif rec.project_id and rec.project_id.partner_id and rec.project_id.partner_id.tax_system_id and rec.project_id.partner_id.tax_system_id.vat_rate is not None:
                # fallback to project partner
                rec.vat_rate = rec.project_id.partner_id.tax_system_id.vat_rate
            else:
                rec.vat_rate = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'project_id' in vals and not vals.get('partner_id'):
                project = self.env['dino.project'].browse(vals['project_id'])
                if project and project.partner_id:
                    vals['partner_id'] = project.partner_id.id
        records = super().create(vals_list)
        
        # Ensure tax system is set for partners after creation
        for record in records:
            if record.partner_id:
                record._ensure_partner_tax_system()
        
        return records

    def write(self, vals):
        result = super().write(vals)
        
        # If partner_id changed, ensure tax system
        if 'partner_id' in vals:
            for record in self:
                if record.partner_id:
                    record._ensure_partner_tax_system()
        
        return result
    
    def _ensure_partner_tax_system(self):
        """
        Ensure partner has tax system set. If not, find or create appropriate tax system.
        Then recompute vat_rate on document.
        """
        self.ensure_one()
        
        if not self.partner_id:
            return
        
        # Check if partner has tax system
        if not self.partner_id.tax_system_id:
            _logger.info(f"Partner {self.partner_id.name} (EGRPOU: {self.partner_id.egrpou}) has no tax system, creating/assigning one")
            
            # Get VAT rate from document if set, otherwise use default
            vat_rate = self.vat_rate if self.vat_rate else 20.0
            
            # Use partner's ensure_tax_system method
            self.partner_id.ensure_tax_system(vat_rate=vat_rate)
        
        # Force recompute vat_rate on document
        self._compute_vat_rate()
        # If project changed and partner not explicitly set, sync partner from project
        res = super().write(vals)
        if 'project_id' in vals and 'partner_id' not in vals:
            for rec in self:
                if rec.project_id and rec.project_id.partner_id:
                    rec.partner_id = rec.project_id.partner_id
        return res

    def action_open_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dino.operation.document',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_copy_json(self):
        """Показать JSON для копирования"""
        self.ensure_one()
        if not self.ocr_result_text:
            raise UserError('JSON пустой, нечего копировать')
        
        # Показать notification с инструкцией
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'JSON готов к копированию',
                'message': 'Выделите весь текст в поле JSON и нажмите Ctrl+C',
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_import_text(self):
        """Импорт номенклатуры из текста или изображения"""
        self.ensure_one()
        
        if not self.import_text_content and not self.import_image:
            raise UserError('Введите текст документа или загрузите изображение для импорта')
        
        # Получить агента парсинга
        if not self.parser_agent_id:
            raise UserError('Выберите агента парсинга')
        
        # Подготовить данные для парсинга
        text_content = ''
        
        if self.import_image:
            # Если есть изображение - сначала извлечь текст через OCR
            from ..services.tesseract_ocr_service import TesseractOCRService
            
            ocr_result = TesseractOCRService.extract_text_from_image(self.import_image)
            
            if not ocr_result['success']:
                raise UserError(f'Ошибка OCR:\n{ocr_result["error"]}')
            
            text_content = ocr_result['text']
            _logger.info(f"OCR extracted text:\n{text_content[:500]}...")  # First 500 chars
            
            # Сохранить распознанный текст в поле (для отладки)
            self.import_text_content = f"<p><b>Распознано через OCR:</b></p><pre>{text_content}</pre>"
        else:
            # Если нет изображения - используем текст из поля
            from odoo.tools import html2plaintext
            text_content = html2plaintext(self.import_text_content) if self.import_text_content else ''
        
        if not text_content.strip():
            raise UserError('Не удалось извлечь текст из документа')
        
        # Этап 1: Парсинг текста через агента (БЕЗ image_data - только текст!)
        partner_name = self.partner_id.name if self.partner_id else None
        parse_result = self.parser_agent_id.parse_text(
            text=text_content,
            partner_name=partner_name,
            image_data=None  # Не передаем изображение - только текст после OCR
        )
        
        if not parse_result['success']:
            error_msg = '\n'.join(parse_result.get('errors', ['Ошибка парсинга']))
            raise UserError(f'Не удалось разобрать документ:\n{error_msg}')
        
        # Этап 2: Обработка JSON через сервис
        from ..services.document_json_service import DocumentJSONService
        
        # Передаємо raw_json для збереження в ocr_result_text
        raw_json = parse_result.get('raw_json', None)
        result = DocumentJSONService.process_parsed_json(self, parse_result, raw_json_str=raw_json)
        
        if not result['success']:
            error_msg = '\n'.join(result.get('errors', ['Ошибка обработки']))
            raise UserError(f'Ошибка обработки данных:\n{error_msg}')
        
        # Формирование сообщения результата
        message = f'Документ: {result["document_number"] or "Н/Д"}\n'
        message += f'Поставщик: {result["supplier_name"]}\n'
        
        if result['partner_found']:
            message += f'Контрагент найден: {self.partner_id.name}\n'
        else:
            message += f'⚠️ Контрагент НЕ найден (создайте вручную)\n'
        
        message += f'\n📝 Создано позиций: {result["created_lines"]}'
        if result['updated_lines'] > 0:
            message += f'\n🔄 Обновлено позиций: {result["updated_lines"]}'
        
        if result['errors']:
            message += f'\n\n❌ Ошибки:\n' + '\n'.join(result['errors'][:5])
            if len(result['errors']) > 5:
                message += f'\n... и ещё {len(result["errors"]) - 5} ошибок'
        
        # Возврат уведомления
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Импорт завершён',
                'message': message,
                'type': 'success' if (result['created_lines'] + result['updated_lines']) > 0 else 'warning',
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window_close',
                },
            }
        }
    
    def action_test_ocr(self):
        """Тестирование OCR - просто извлечь текст из изображения"""
        self.ensure_one()
        
        from ..services.tesseract_ocr_service import TesseractOCRService
        
        # Извлечь изображение из HTML поля или Binary поля
        image_data = None
        
        if self.import_image:
            # Прямая загрузка файла
            image_data = self.import_image
            _logger.info("=== OCR: Используется загруженный файл")
            
        elif self.import_text_content:
            # Извлечь изображение из HTML
            result, source_type = TesseractOCRService.extract_image_from_html(self.import_text_content)
            
            if source_type == 'base64':
                image_data = result
                _logger.info("=== OCR: Извлечено base64 изображение из HTML")
                
            elif source_type == 'attachment':
                # result содержит attachment_id
                image_data = TesseractOCRService.extract_image_from_odoo_attachment(self.env, result)
                _logger.info(f"=== OCR: Извлечено изображение из attachment {result}")
        
        if not image_data:
            raise UserError('Изображение не найдено. Вставьте скриншот или загрузите файл.')
        
        # Распознать текст через OCR - умное распознавание с несколькими языками
        ocr_result = TesseractOCRService.extract_text_smart(image_data)
        
        if not ocr_result['success']:
            raise UserError(f'Ошибка OCR:\n{ocr_result["error"]}')
        
        # Сохранить результат в поле примечаний
        extracted_text = ocr_result['text']
        stats = ocr_result.get('stats', {})
        lang_used = ocr_result.get('lang_used', 'unknown')
        
        # Вывести результат в поле "Примечания" на вкладке Notes
        separator = "="*60 + "\n📝 РЕЗУЛЬТАТ OCR:\n" + "="*60
        stats_info = f"\n📊 Статистика: {stats.get('char_count', 0)} символов, {stats.get('line_count', 0)} строк"
        stats_info += f"\n🌐 Языки: {lang_used}\n"
        
        # Добавить OCR текст к существующим примечаниям
        from odoo.tools.mail import html2plaintext
        current_notes = html2plaintext(self.notes) if self.notes else ''
        
        if current_notes.strip():
            new_notes = current_notes + "\n\n" + separator + stats_info + "\n" + extracted_text
        else:
            new_notes = separator + stats_info + "\n" + extracted_text
        
        self.notes = f"<pre>{new_notes}</pre>"
        
        # Также сохранить в служебное поле для тестирования
        self.ocr_result_text = extracted_text
        
        # Перезагрузить форму на вкладку Notes
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dino.operation.document',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                **self.env.context,
                'ocr_success_message': f'✅ OCR завершён! Распознано {len(extracted_text)} символов. Результат в примечаниях.',
            },
        }
