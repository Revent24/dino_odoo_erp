# --- МОДЕЛЬ: Project Document (dino.operation.document)
# --- ФАЙЛ: models/dino_operation_document.py

from odoo import fields, models, api


class DinoOperationDocument(models.Model):
    _name = 'dino.operation.document'
    _description = 'Project Document'
    _order = 'sequence, id'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mixin.auto.translate']
    _rec_name = 'number'

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
    document_type = fields.Selection(
        selection=[
            ('quotation', 'Quotation'),
            ('order', 'Order'),
            ('invoice', 'Invoice'),
            ('waybill', 'Waybill'),
            ('payment_order', 'Payment Order'),
            ('other', 'Other'),
        ],
        string='Type'
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
        store=True,
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
        return records

    def write(self, vals):
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
