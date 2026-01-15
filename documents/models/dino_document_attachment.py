#
#  -*- File: documents/models/dino_document_attachment.py -*-
#
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io
import logging

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None


class DinoDocumentAttachment(models.Model):
    _name = 'dino.document.attachment'
    _description = 'Document Attachment for Import'
    _order = 'create_date desc'
    _rec_name = 'filename'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # === ОСНОВНЫЕ ПОЛЯ ===
    document_id = fields.Many2one(
        'dino.operation.document',
        string='Document',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    file_data = fields.Binary(
        string='File',
        required=True,
        attachment=True
    )
    
    filename = fields.Char(
        string='Filename',
        required=True
    )
    
    file_type = fields.Selection(
        selection=[
            ('excel', 'Excel (.xlsx, .xls)'),
            ('csv', 'CSV'),
            ('xml', 'XML'),
            ('json', 'JSON'),
            ('pdf', 'PDF'),
            ('other', 'Other'),
        ],
        string='File Type',
        compute='_compute_file_type',
        store=True
    )
    
    parser_type = fields.Selection(
        selection=[
            ('sapriz', 'Sapriz Invoice (1C)'),
            ('universal', 'Universal Template'),
            ('csv_auto', 'CSV Auto-detect'),
            ('xml_upd', 'XML УПД'),
            ('xml_generic', 'XML Generic'),
            ('custom', 'Custom'),
        ],
        string='Parser Type',
        default='sapriz'
    )
    
    # === СТАТУС ИМПОРТА ===
    import_status = fields.Selection(
        selection=[
            ('draft', 'Not Imported'),
            ('importing', 'Importing...'),
            ('imported', 'Imported'),
            ('error', 'Error'),
        ],
        string='Import Status',
        default='draft',
        required=True,
        index=True
    )
    
    imported_lines_count = fields.Integer(
        string='Imported Lines',
        default=0,
        readonly=True
    )
    
    import_date = fields.Datetime(
        string='Import Date',
        readonly=True
    )
    
    error_log = fields.Text(
        string='Error Log',
        readonly=True
    )
    
    # === НАСТРОЙКИ ===
    auto_import_on_create = fields.Boolean(
        string='Auto Import on Upload',
        default=False,
        help='Automatically import file after upload'
    )
    
    replace_existing = fields.Boolean(
        string='Replace Existing Lines',
        default=False,
        help='Delete existing specification lines before import'
    )

    # === ВЫЧИСЛЯЕМЫЕ ПОЛЯ ===
    @api.depends('filename')
    def _compute_file_type(self):
        """Определение типа файла по расширению"""
        for record in self:
            if not record.filename:
                record.file_type = 'other'
                continue
            
            ext = record.filename.lower().split('.')[-1]
            
            if ext in ['xlsx', 'xls']:
                record.file_type = 'excel'
            elif ext == 'csv':
                record.file_type = 'csv'
            elif ext == 'xml':
                record.file_type = 'xml'
            elif ext == 'json':
                record.file_type = 'json'
            elif ext == 'pdf':
                record.file_type = 'pdf'
            else:
                record.file_type = 'other'

    # === МЕТОДЫ ИМПОРТА ===
    def action_import(self):
        """Выполнить импорт файла"""
        self.ensure_one()
        
        if not self.file_data:
            raise UserError(_('No file uploaded'))
        
        if not self.document_id:
            raise UserError(_('Document not specified'))
        
        try:
            self.write({'import_status': 'importing', 'error_log': False})
            
            # Выбор парсера на основе типа файла и парсера
            if self.file_type == 'excel':
                lines_count = self._import_excel()
            elif self.file_type == 'csv':
                lines_count = self._import_csv()
            elif self.file_type == 'xml':
                lines_count = self._import_xml()
            elif self.file_type == 'json':
                lines_count = self._import_json()
            else:
                raise UserError(_('File type "%s" is not supported for import') % self.file_type)
            
            # Успешный импорт
            self.write({
                'import_status': 'imported',
                'imported_lines_count': lines_count,
                'import_date': fields.Datetime.now(),
                'error_log': False
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('%s lines imported successfully from %s') % (lines_count, self.filename),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            _logger.error('Import error for file %s: %s', self.filename, error_msg)
            
            self.write({
                'import_status': 'error',
                'error_log': error_msg
            })
            
            raise UserError(_('Import failed: %s') % error_msg)

    def _import_excel(self):
        """Импорт из Excel файла"""
        if not openpyxl:
            raise UserError(_("Python library 'openpyxl' is not installed"))
        
        # Использовать существующую логику из wizard
        # Создать временный wizard для использования его методов
        wizard = self.env['dino.import.specification.excel'].create({
            'file_data': self.file_data,
            'filename': self.filename,
            'parser_type': self.parser_type if self.parser_type in ['sapriz', 'universal'] else 'sapriz'
        })
        
        # Запомнить количество строк до импорта
        lines_before = len(self.document_id.specification_ids)
        
        # Вызвать импорт с контекстом документа
        result = wizard.with_context(
            active_id=self.document_id.id,
            replace_existing=self.replace_existing
        ).action_import()
        
        # Подсчитать новые импортированные строки
        lines_after = len(self.document_id.specification_ids)
        lines_count = lines_after - lines_before if not self.replace_existing else lines_after
        
        return lines_count

    def _import_csv(self):
        """Импорт из CSV файла"""
        raise UserError(_('CSV import is not yet implemented'))

    def _import_xml(self):
        """Импорт из XML файла"""
        raise UserError(_('XML import is not yet implemented'))

    def _import_json(self):
        """Импорт из JSON файла"""
        raise UserError(_('JSON import is not yet implemented'))

    def action_reset(self):
        """Сброс статуса для повторного импорта"""
        self.ensure_one()
        self.write({
            'import_status': 'draft',
            'import_date': False,
            'imported_lines_count': 0,
            'error_log': False
        })

    def action_view_document(self):
        """Открыть связанный документ"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dino.operation.document',
            'res_id': self.document_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # === АВТОМАТИЧЕСКИЙ ИМПОРТ ===
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        
        # Автоимпорт при создании
        for record in records:
            if record.auto_import_on_create:
                try:
                    record.action_import()
                except Exception as e:
                    _logger.warning('Auto-import failed for %s: %s', record.filename, str(e))
        
        return records

    def unlink(self):
        """Предупреждение при удалении импортированных файлов"""
        if any(rec.import_status == 'imported' for rec in self):
            raise UserError(_('Cannot delete imported attachments. Reset import status first.'))
        return super().unlink()
# End of file documents/models/dino_document_attachment.py
