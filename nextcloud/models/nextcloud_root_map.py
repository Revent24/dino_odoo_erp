# -*- File: nextcloud/models/nextcloud_root_map.py -*-
from odoo import models, fields, api

class NextcloudRootMap(models.Model):
    _name = 'nextcloud.root.map'
    _description = 'Nextcloud Root Map'

    client_id = fields.Many2one('nextcloud.client', string='Client', required=True, ondelete='cascade')
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    res_id = fields.Integer(string='Resource ID', required=True)
    
    # Имя папки (берется из имени категории Odoo)
    folder_name = fields.Char(string="Название папки", required=True)
    folder_id = fields.Many2one('nextcloud.file', string="Папка NC")
    folder_file_id = fields.Char(related='folder_id.file_id', string="ID NC", readonly=True)
    folder_path = fields.Char(related='folder_id.path', string="Путь", readonly=True)

    _sql_constraints = [
        ('unique_mapping', 'unique(client_id, model_id, res_id)', 'Маппинг уже существует!')
    ]
# End of file nextcloud/models/nextcloud_root_map.py