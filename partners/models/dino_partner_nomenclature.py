#
#  -*- File: partners/models/dino_partner_nomenclature.py -*-
#
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DinoPartnerNomenclature(models.Model):
    _name = 'dino.partner.nomenclature'
    _description = 'Partner Nomenclature Mapping'
    _order = 'partner_id, sequence, id'

    partner_id = fields.Many2one('dino.partner', string='Partner', required=True, ondelete='cascade')
    name = fields.Char(string='Supplier Item Name', required=True, translate=True)
    nomenclature_id = fields.Many2one('dino.nomenclature', string='Internal Nomenclature', ondelete='restrict')
    dino_uom_id = fields.Many2one('dino.uom', string='Document Unit', help='Unit of measure from supplier documents')
    warehouse_uom_id = fields.Many2one(
        'dino.uom', 
        string='Warehouse Unit', 
        help='Unit of measure for warehouse operations. Defaults to document unit, but can be changed.'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    
    # Computed field for document count
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count',
        store=True,
        help='Number of documents that reference this partner nomenclature item'
    )

    _sql_constraints = [
        ('partner_name_uniq', 'UNIQUE(partner_id, name)', 'Supplier item name must be unique per partner'),
    ]
    
    @api.depends('active')  # We depend on active to trigger recompute when status changes
    def _compute_document_count(self):
        """Compute the number of documents that reference this partner nomenclature item"""
        for record in self:
            record.document_count = self.env['dino.operation.document.specification'].search_count([
                ('supplier_nomenclature_id', '=', record.id)
            ])

    @api.onchange('dino_uom_id')
    def _onchange_dino_uom_id(self):
        """Auto-fill warehouse_uom_id with document unit if not set"""
        if self.dino_uom_id and not self.warehouse_uom_id:
            self.warehouse_uom_id = self.dino_uom_id

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.nomenclature_id:
                label = "%s → %s" % (rec.name, rec.nomenclature_id.name)
            res.append((rec.id, label))
        return res

    @api.model
    def find_or_create(self, partner_id, supplier_name, auto_create=True, uom_id=None):
        """
        Найти или создать запись в справочнике номенклатуры контрагента
        
        :param partner_id: ID контрагента
        :param supplier_name: Название позиции у поставщика
        :param auto_create: Автоматически создавать если не найдено
        :param uom_id: ID единицы измерения (опционально)
        :return: запись dino.partner.nomenclature или False
        """
        if not partner_id or not supplier_name:
            return False
        
        # Поиск существующей записи
        nomenclature = self.search([
            ('partner_id', '=', partner_id),
            ('name', '=', supplier_name)
        ], limit=1)
        
        # Создание новой записи если не найдено и разрешено
        if not nomenclature and auto_create:
            vals = {
                'partner_id': partner_id,
                'name': supplier_name,
            }
            if uom_id:
                vals['dino_uom_id'] = uom_id
                vals['warehouse_uom_id'] = uom_id  # Default to same unit
            
            nomenclature = self.create(vals)
        
        return nomenclature

    def unlink(self):
        """Prevent deletion if there are linked documents"""
        for record in self:
            if record.document_count > 0:
                raise ValidationError(
                    _("Cannot delete partner nomenclature '%s' because it is referenced by %d document(s). "
                      "Deletion is only allowed from the document interface.") % 
                    (record.name, record.document_count)
                )
        return super().unlink()
# End of file partners/models/dino_partner_nomenclature.py
