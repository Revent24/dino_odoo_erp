from odoo import api, fields, models, _


class DinoPartnerNomenclature(models.Model):
    _name = 'dino.partner.nomenclature'
    _description = 'Partner Nomenclature Mapping'
    _order = 'partner_id, sequence, id'

    partner_id = fields.Many2one('dino.partner', string='Partner', required=True, ondelete='cascade')
    name = fields.Char(string='Supplier Item Name', required=True, translate=True)
    nomenclature_id = fields.Many2one('dino.nomenclature', string='Internal Nomenclature', ondelete='restrict')
    uom_id = fields.Many2one('uom.uom', string='Unit')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('partner_name_uniq', 'UNIQUE(partner_id, name)', 'Supplier item name must be unique per partner'),
    ]

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.nomenclature_id:
                label = "%s → %s" % (rec.name, rec.nomenclature_id.name)
            res.append((rec.id, label))
        return res
