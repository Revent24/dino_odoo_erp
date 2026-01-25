# -*- File: projects/models/dino_project.py -*-
import logging
from odoo import api, fields, models, _
from odoo.addons.dino_erp.nextcloud.tools.nextcloud_api import NextcloudConnector

_logger = logging.getLogger(__name__)

class DinoProject(models.Model):
    _name = 'dino.project'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'nextcloud.file.project.mixin']
    _description = _('Project')

    name = fields.Char(string=_('Project Name'), required=True)
    date = fields.Date(string=_('Date'), required=True, default=fields.Date.today)
    project_category_id = fields.Many2one('dino.project.category', string=_('Категория проекта'), required=True)

    # Ссылка на категорию Проекта
    project_type_id = fields.Many2one('dino.project.type', string=_('Класс проекта'), required=True, index=True, tracking=True, 
                                     domain="[('project_category_id', '=', project_category_id)]")
    
    # Related поле для места хранения документов
    storage_location = fields.Char(string=_('Место хранения документов'), related='project_category_id.storage_location', readonly=True, store=False)

    # Reference to linked order (sale or purchase)
    order_ref = fields.Reference(selection=[('sale.order', 'Sale Order'), ('purchase.order', 'Purchase Order')], string=_('Linked Order'))

    # Link to partner
    partner_id = fields.Many2one('dino.partner', string=_('Partner'))

    # Documents link
    document_ids = fields.One2many('dino.operation.document', 'project_id', string='Documents')
    document_count = fields.Integer(string='Documents Count', compute='_compute_document_count')

    # Payments link
    payment_ids = fields.One2many('dino.project.payment', 'project_id', string=_('Payments'))
    payment_count = fields.Integer(string=_('Payments Count'), compute='_compute_payment_count')

    # VAT rate
    vat_rate = fields.Float(string='VAT Rate (%)', related='partner_id.tax_system_id.vat_rate', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("NC_DEBUG: Start create projects. Count: %s", len(vals_list))
        records = super(DinoProject, self).create(vals_list)
        for record in records:
            _logger.info("NC_DEBUG: Project created [ID: %s]. Triggering NC folder creation...", record.id)
            # Автоматически создаем папку при сохранении нового проекта
            try:
                record.action_ensure_nc_folder()
            except Exception as e:
                _logger.error("NC_DEBUG: Failed to auto-create folder: %s", str(e))
        return records

    def write(self, vals):
        # Логика перемещения/переименования теперь в NextcloudProjectMixin.write
        return super(DinoProject, self).write(vals)

    # _sync_nc_folder_location удален, так как Logic v.2.0 работает через миксин
        self.nc_folder_id.with_context(no_nextcloud_move=True).write({
            'name': new_name,
            'path': new_path,
            'file_id': new_id
        })

    def _compute_document_count(self):
        for rec in self:
            if 'dino.operation.document' in self.env:
                rec.document_count = self.env['dino.operation.document'].search_count([('project_id', '=', rec.id)])
            else:
                rec.document_count = 0

    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = self.env['dino.project.payment'].search_count([('project_id', '=', rec.id)])

    def action_view_documents(self):
        self.ensure_one()
        return {
            'name': _('Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.operation.document',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.project.payment',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    @api.onchange('order_ref')
    def _onchange_order_ref(self):
        val = self.order_ref
        model = False
        try:
            if hasattr(val, '_name'): model = val._name
            elif isinstance(val, tuple): model = val[0]
            elif isinstance(val, str) and ',' in val: model = val.split(',')[0]
        except Exception: model = False

        if model == 'sale.order':
            income_cat = self.env['dino.project.category'].search([('code', '=', 'income')], limit=1)
            if income_cat: self.project_category_id = income_cat
        elif model == 'purchase.order':
            expense_cat = self.env['dino.project.category'].search([('code', '=', 'expense')], limit=1)
            if expense_cat: self.project_category_id = expense_cat
        else:
            if not self.project_category_id:
                expense_cat = self.env['dino.project.category'].search([('code', '=', 'expense')], limit=1)
                if expense_cat: self.project_category_id = expense_cat  
# end of projects/models/dino_project.py