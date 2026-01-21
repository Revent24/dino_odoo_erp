# -*- File: nextcloud/mixins/nextcloud_flat_mixin.py -*-
from odoo import models, fields, api

class NextcloudFlatMixin(models.AbstractModel):
    _name = 'nextcloud.file.flat.mixin'
    _inherit = 'nextcloud.file.base.mixin'

    def action_ensure_nc_folder(self):
        self.ensure_one()
        if self.nc_folder_id: return self.nc_folder_id
        
        client = self._get_nc_client()
        # Ищем корень модели (напр. "Партнеры")
        root_map = self.env['nextcloud.root.map'].search([
            ('model_id.model', '=', self._name),
            ('client_id', '=', client.id)
        ], limit=1)
        
        # Если корня нет - создаем в '/'
        if not root_map:
            from ..tools.nextcloud_api import NextcloudConnector
            path, nc_id = NextcloudConnector.ensure_path(client, [self._description], '/')
            folder = self._create_nc_record(client, self._description, nc_id, path)
            root_map = self.env['nextcloud.root.map'].create({
                'client_id': client.id,
                'name': self._description,
                'model_id': self.env['ir.model'].search([('model', '=', self._name)]).id,
                'folder_id': folder.id
            })

        # Создаем папку записи
        from ..tools.nextcloud_api import NextcloudConnector
        path, nc_id = NextcloudConnector.ensure_path(client, [self.display_name], root_map.path)
        self.nc_folder_id = self._create_nc_record(client, self.display_name, nc_id, path, root_map.folder_id.id)
        return self.nc_folder_id
# -*- End of file nextcloud/mixins/nextcloud_flat_mixin.py -*-
