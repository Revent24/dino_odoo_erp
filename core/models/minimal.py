from odoo import models, fields


class DinoMinimal(models.Model):
    _name = "dino.minimal"
    _description = "Минимальная модель"

    name = fields.Char(string="Название", required=True)