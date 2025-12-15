from odoo import api, fields, models, _


class DinoProject(models.Model):
    _name = 'dino.project'
    _description = _('Project')

    name = fields.Char(string=_('Project Name'), required=True)
    date = fields.Date(string=_('Date'), required=True, default=fields.Date.today)
