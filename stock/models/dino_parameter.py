# --- МОДЕЛЬ: ПАРАМЕТРЫ НОМЕНКЛАТУРЫ
# --- ФАЙЛ: models/dino_parameter.py
#

from odoo import fields, models, _, api

class DinoParameter(models.Model):
    _name = 'dino.parameter'
    _description = 'Technical Parameter'
    _order = 'sequence, id'
    _inherit = ['mixin.auto.translate']

    # Привязка к конкретному исполнению
    nomenclature_id = fields.Many2one('dino.nomenclature', string=_('Nomenclature'), required=True, ondelete='cascade')
    
    sequence = fields.Integer(string=_('Sequence'), default=10)
    
    # Само значение параметра
    name = fields.Char(string=_('Parameter Name'), required=True, translate=True) # Напр. "Длина"
    value = fields.Float(string=_('Value'), default=0.0, required=True)           # Напр. 810
    uom_id = fields.Many2one('dino.uom', string=_('Unit'))                         # Напр. мм

# --- END ---