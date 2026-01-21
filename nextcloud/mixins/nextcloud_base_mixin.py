# -*- File: nextcloud/mixins/nextcloud_base_mixin.py -*-
from odoo import models, fields

class NextcloudBaseMixin(models.AbstractModel):
    _name = 'nextcloud.file.base.mixin'
    
    nc_folder_id = fields.Many2one('nextcloud.file', string='NC Folder', ondelete='set null', copy=False)

    def _get_nc_client(self):
        return self.env['nextcloud.client'].search([('user_id', '=', False), ('state', '=', 'confirmed')], limit=1)

    def _create_nc_record(self, client, name, nc_id, path, parent_id=False):
        """Универсальный метод создания записи в нашей таблице файлов"""
        return self.env['nextcloud.file'].create({
            'name': name,
            'file_id': nc_id,
            'path': path,
            'file_type': 'dir',
            'client_id': client.id,
            'parent_id': parent_id,
        })
# -*- End of file nextcloud/mixins/nextcloud_base_mixin.py -*-