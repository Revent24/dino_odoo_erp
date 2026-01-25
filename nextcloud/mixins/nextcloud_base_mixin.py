# -*- File: nextcloud/mixins/nextcloud_base_mixin.py -*-
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

class NextcloudBaseMixin(models.AbstractModel):
    _name = 'nextcloud.file.base.mixin'
    
    nc_folder_id = fields.Many2one('nextcloud.file', string='NC Folder', ondelete='set null', copy=False)
    nc_file_id = fields.Integer("Nextcloud File ID", index=True)
    nc_path = fields.Char("Nextcloud Path")

    def _get_nc_client(self):
        return self.env['nextcloud.client'].search([('state', '=', 'confirmed')], limit=1)

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

    def _get_nc_connector(self):
        """
        Получает активный коннектор Nextcloud из конфигурации.
        """
        client = self.env['nextcloud.client'].search([('state', '=', 'confirmed')], limit=1)
        if not client:
            _logger.warning("Активный клиент Nextcloud не найден.")
            return False
        return client._get_connector()

    def _update_nc_path(self):
        """
        Обновляет путь к файлу/папке в Nextcloud на основе file_id (v.2.0).
        """
        for record in self:
            if not record.nc_file_id:
                continue

            connector = record._get_nc_connector()
            if connector:
                try:
                    data = connector.get_object_data(file_id=record.nc_file_id)
                    if data:
                        record.nc_path = data['href']
                except Exception as e:
                    _logger.error("Failed to update NC path for ID %s: %s", record.nc_file_id, e)
        return True
# -*- End of file nextcloud/mixins/nextcloud_base_mixin.py -*-