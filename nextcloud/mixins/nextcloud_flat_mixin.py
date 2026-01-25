# -*- File: nextcloud/mixins/nextcloud_flat_mixin.py -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class NextcloudFlatMixin(models.AbstractModel):
    _name = 'nextcloud.file.flat.mixin'
    _inherit = 'nextcloud.file.base.mixin'

    def action_ensure_nc_folder(self):
        """
        Создает или находит папку для записи модели в корне 'Odoo Docs' (v.2.0).
        """
        self.ensure_one()
        if self.nc_folder_id: 
            return self.nc_folder_id
        
        client = self._get_nc_client()
        if not client or not client.root_folder_id:
            _logger.warning("NC Build: Client or Root Folder not ready.")
            return

        connector = client._get_connector()
        root_id = int(client.root_folder_id)
        
        # 1. Обеспечиваем папку модели в Odoo Docs
        model_name = self._description or self._name
        model_root_id = connector.ensure_path_step(root_id, model_name)
        
        # 2. Проверяем наличие nextcloud.root.map
        root_map = self.env['nextcloud.root.map'].search([
            ('model_id.model', '=', self._name),
            ('client_id', '=', client.id)
        ], limit=1)
        
        if not root_map:
            model_info = connector.get_object_data(file_id=model_root_id)
            root_folder_rec = self._create_nc_record(client, model_name, model_root_id, model_info['href'])
            root_map = self.env['nextcloud.root.map'].create({
                'client_id': client.id,
                'model_id': self.env['ir.model'].search([('model', '=', self._name)]).id,
                'folder_id': root_folder_rec.id,
                'folder_name': model_name
            })

        # 3. Обеспечиваем папку конкретной записи
        record_label = f"{self.display_name} [{self.id}]"
        record_folder_id = connector.ensure_path_step(model_root_id, record_label)
        record_info = connector.get_object_data(file_id=record_folder_id)
        
        if record_info:
            folder_rec = self._create_nc_record(
                client, record_label, record_folder_id, 
                record_info['href'], root_map.folder_id.id
            )
            self.write({'nc_folder_id': folder_rec.id})
            return folder_rec
        
        return False
# -*- End of file nextcloud/mixins/nextcloud_flat_mixin.py -*-
