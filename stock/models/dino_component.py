# --- МОДЕЛЬ: КОМПОНЕНТ (СЕМЕЙСТВО / РОДИТЕЛЬ)
# --- ФАЙЛ: models/dino_component.py
#

from odoo import fields, models, _, api
from odoo.exceptions import ValidationError

class DinoComponent(models.Model):
    _name = 'dino.component'
    _description = 'Component Family'
    _inherit = ['image.mixin', 'mail.thread', 'mail.activity.mixin', 'mixin.auto.translate']

    active = fields.Boolean(default=True)
    name = fields.Char(string=_('Family Name'), required=True, translate=True, tracking=True)
    category_id = fields.Many2one('dino.component.category', string=_('Category'), tracking=True)
    uom_id = fields.Many2one(
        'dino.uom',
        string=_('Unit of Measure'),
        required=False,
    )
    nomenclature_ids = fields.One2many('dino.nomenclature', 'component_id', string=_('Nomenclatures'))
    
    # ЗАМЕТКИ
    description = fields.Html(string=_('Internal Notes'), translate=True)
    is_favorite = fields.Boolean(string=_('Favorite'))

    # === НОВОЕ: ПОДСЧЕТ И КНОПКА ===
    nomenclature_count = fields.Integer(compute='_compute_nomenclature_count')

    def _compute_nomenclature_count(self):
        for rec in self:
            rec.nomenclature_count = len(rec.nomenclature_ids)

    def action_view_nomenclatures(self):
        self.ensure_one()
        return {
            'name': _('Nomenclatures'),
            'type': 'ir.actions.act_window',
            'res_model': 'dino.nomenclature',
            'view_mode': 'list,form',
            'domain': [('component_id', '=', self.id)],
            'context': {'default_component_id': self.id}, 
        }
    # ===============================

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Component Family name must be unique!'),
    ]

    @api.constrains('name')
    def _check_name_unique(self):
        """Проверка уникальности наименования компонента"""
        for rec in self:
            if rec.name:
                domain = [('name', '=', rec.name), ('id', '!=', rec.id)]
                if self.search_count(domain) > 0:
                    raise ValidationError(_('Component with name "%s" already exists! Please use a unique name.') % rec.name)

    def toggle_is_favorite(self):
        for rec in self:
            rec.is_favorite = not rec.is_favorite

# --- END ---