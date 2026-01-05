from odoo import api, fields, models, _


class DinoProject(models.Model):
    _name = 'dino.project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = _('Project')

    name = fields.Char(string=_('Project Name'), required=True)
    date = fields.Date(string=_('Date'), required=True, default=fields.Date.today)

    # Classification fields for project routing
    project_type = fields.Selection([
        ('sale', 'Sales'),
        ('purchase', 'Purchases'),
        ('overhead', 'Overhead')
    ], string=_('Project Type'), default=False, required=True, index=True, tracking=True)

    # Reference to linked order (sale or purchase) without requiring external modules
    order_ref = fields.Reference(selection=[('sale.order', 'Sale Order'), ('purchase.order', 'Purchase Order')], string=_('Linked Order'))

    # Link to partner (dino.partner)
    partner_id = fields.Many2one('dino.partner', string=_('Partner'))

    # Documents link: one2many, count and action
    document_ids = fields.One2many('dino.operation.document', 'project_id', string='Documents')
    document_count = fields.Integer(string='Documents Count', compute='_compute_document_count')

    # Payments link: one2many, count and action
    payment_ids = fields.One2many('dino.project.payment', 'project_id', string=_('Payments'))
    payment_count = fields.Integer(string=_('Payments Count'), compute='_compute_payment_count')

    # VAT rate for project derived from partner.tax_system
    vat_rate = fields.Float(string='VAT Rate (%)', related='partner_id.tax_system_id.vat_rate', readonly=True)

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
        """Auto-set project_type based on linked order reference (works even if sale/purchase modules are not installed)."""
        val = self.order_ref
        model = False
        try:
            # Record proxy
            if hasattr(val, '_name'):
                model = val._name
            elif isinstance(val, tuple):
                model = val[0]
            elif isinstance(val, str) and ',' in val:
                model = val.split(',')[0]
        except Exception:
            model = False

        if model == 'sale.order':
            self.project_type = 'sale'
        elif model == 'purchase.order':
            self.project_type = 'purchase'
        else:
            if not (self.project_type in ('sale', 'purchase')):
                self.project_type = 'overhead'
