from odoo import api, fields, models, _


class DinoProject(models.Model):
    _name = 'dino.project'
    _description = _('Project')

    name = fields.Char(string=_('Project Name'), required=True)
    date = fields.Date(string=_('Date'), required=True, default=fields.Date.today)

    # Classification fields for project routing
    project_type = fields.Selection([
        ('sale', 'Sales'),
        ('purchase', 'Purchases'),
        ('overhead', 'Overhead')
    ], string=_('Project Type'), default=False, required=True, index=True)

    # Reference to linked order (sale or purchase) without requiring external modules
    order_ref = fields.Reference(selection=[('sale.order', 'Sale Order'), ('purchase.order', 'Purchase Order')], string=_('Linked Order'))

    # Link to partner (dino.partner)
    partner_id = fields.Many2one('dino.partner', string=_('Partner'))

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
