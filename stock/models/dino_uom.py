from odoo import fields, models, api, _

class DinoUoM(models.Model):
    _name = 'dino.uom'
    _description = 'Dino Unit of Measure'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    rounding = fields.Float(string='Rounding', default=0.01)
    active = fields.Boolean(default=True)
    
    # Conversion fields
    conversion_factor = fields.Float(
        string='Conversion Factor',
        default=1.0,
        help='Factor to convert from this unit to the related unit (e.g., 1 kg = 1000 g, factor = 1000)'
    )
    related_uom_id = fields.Many2one(
        'dino.uom',
        string='Related Unit',
        help='Related unit of measure for conversion (e.g., kg → g)'
    )
    
    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Unit name must be unique'),
        ('conversion_factor_positive', 'CHECK(conversion_factor > 0)', 'Conversion factor must be positive'),
    ]
    
    @api.model
    def find_or_create(self, unit_name):
        """
        Find or create unit of measure by name
        
        :param unit_name: Name of the unit
        :return: dino.uom record or False
        """
        if not unit_name:
            return False
        
        # Search for existing unit (case-insensitive)
        uom = self.search([('name', '=ilike', unit_name)], limit=1)
        
        # Create new unit if not found
        if not uom:
            uom = self.create({
                'name': unit_name.strip(),
            })
        
        return uom
