# --- МОДЕЛЬ: Project Document (dino.operation.document)
# --- ФАЙЛ: models/dino_operation_document.py

from odoo import fields, models, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)
from ..services.image_utils import prepare_inline_data, safe_truncate


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
    notes = fields.Text(
        string='Notes'
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

    def action_open_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dino.operation.document',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    # JSON copy action removed (ocr_result_text field deleted)
    
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
        image_data = None
        
        if self.import_image:
            # Используем image_utils.prepare_inline_data для нормализации и определения формата
            try:
                inline = prepare_inline_data(self.import_image)
                if inline:
                    image_data = inline.get('data')
                    _logger.info(f"Using image from import_image (mime={inline.get('mime_type')}, {len(image_data) if image_data else 0} chars)")
                else:
                    _logger.warning("prepare_inline_data returned None for import_image")
            except Exception as e:
                _logger.warning(f"prepare_inline_data error for import_image: {e}")
        else:
            # Если нет изображения в поле - ищем в HTML
            import re
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', self.import_text_content or '')

            if img_match:
                img_src = img_match.group(1)
                _logger.info(f"Found image in HTML: {img_src[:100]}")

                if img_src.startswith('data:'):
                    inline = prepare_inline_data(img_src)
                    if inline:
                        image_data = inline.get('data')
                        _logger.info(f"Extracted inline image from HTML (mime={inline.get('mime_type')})")
                elif img_src.startswith('/web/image'):
                    attachment_id = None
                    id_match = re.search(r'/web/image/(\d+)', img_src)
                    if id_match:
                        attachment_id = int(id_match.group(1))
                        _logger.info(f"Found attachment ID: {attachment_id}")

                        Attachment = self.env['ir.attachment'].sudo()
                        attachment = Attachment.browse(attachment_id)

                        if attachment and attachment.exists():
                            att_data = attachment.datas
                            if att_data:
                                inline = prepare_inline_data(att_data)
                                if inline:
                                    image_data = inline.get('data')
                                    _logger.info(f"Loaded image from attachment id {attachment_id} (mime={inline.get('mime_type')})")
                                else:
                                    _logger.warning(f"prepare_inline_data failed for attachment {attachment_id}")
                            else:
                                raise UserError(f'Вкладення {attachment_id} не містить даних')
                        else:
                            raise UserError(f'Вкладення з ID {attachment_id} не знайдено')
                    else:
                        raise UserError(f'Не вдається витягти ID з посилання: {img_src[:100]}')

            # Якщо є текст в полі (і немає зображення) - використовуємо його
            if not image_data and self.import_text_content:
                from odoo.tools import html2plaintext
                text_content = html2plaintext(self.import_text_content)
        
        if not text_content.strip() and not image_data:
            raise UserError('Не удалось извлечь текст или изображение из документа')
        
        # Логирование что именно будет парситься
        parsing_mode = ""
        if image_data and text_content:
            parsing_mode = f"🔄 Image + Text ({len(text_content)} chars)"
            _logger.info(f"🔄 Parsing MODE: Image + Text ({len(text_content)} chars)")
        elif image_data:
            parsing_mode = "🖼️ Image only"
            _logger.info(f"🖼️ Parsing MODE: Image only")
        elif text_content:
            parsing_mode = f"📝 Text only ({len(text_content)} chars)"
            _logger.info(f"📝 Parsing MODE: Text only ({len(text_content)} chars)")
        
        # ✅ Зберегти початкову інформацію ПЕРЕД викликом API
        partner_name = self.partner_id.name if self.partner_id else None
        pre_notes = f"=== 🔄 Підготовка запиту ===\n"
        pre_notes += f"Mode: {parsing_mode}\n"
        if text_content:
            pre_notes += f"Text: {len(text_content)} chars\n"
        if image_data:
            pre_notes += f"Image: {type(image_data).__name__}, {len(image_data)} length\n"
        if partner_name:
            pre_notes += f"Partner: {partner_name}\n"
        self.write({'notes': pre_notes})
        
        # Этап 1: Парсинг через агента (передаём изображение ИЛИ текст)
        parse_result = self.parser_agent_id.parse_text(
            text=text_content if text_content else None,
            image_data=image_data,  # Передаём изображение напрямую в AI
            partner_name=partner_name
        )
        
        if not parse_result['success']:
            error_msg = '\n'.join(parse_result.get('errors', ['Ошибка парсинга']))
            raise UserError(f'Не удалось разобрать документ:\n{error_msg}')
        
        # 🔍 ДІАГНОСТИКА: Зберегти повний текст запиту в notes документа (завжди)
        if parse_result.get('debug_info'):
            full_request = parse_result['debug_info'].get('full_request', '')
            # Обрізаємо до 10000 символів щоб швидше
            full_request = safe_truncate(full_request, 10000)
            self.write({'notes': full_request})
        else:
            # Якщо немає debug_info - принаймні покажемо що запит був
            self.write({'notes': f'Запит відправлено. Tokens: {parse_result.get("tokens_used", 0)}'})
        
        # Этап 2: Обработка JSON через сервис
        from ..services.document_json_service import DocumentJSONService
        
        # Передаємо parsed JSON в сервіс для обробки
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
    
    
