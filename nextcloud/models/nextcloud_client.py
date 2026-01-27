# -*- File: nextcloud/models/nextcloud_client.py -*-

import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from ..tools.nextcloud_api import NextcloudConnector

_logger = logging.getLogger(__name__)

class NextcloudClient(models.Model):
    _name = 'nextcloud.client'
    _description = 'Nextcloud Client Configuration'
    
    name = fields.Char(string='Config Name', required=True, default='Local Nextcloud')
    url = fields.Char(string='Base URL', required=True, default='http://localhost:8080')
    username = fields.Char(string='Username', required=True, default='admin')
    password = fields.Char(string='Password', required=True, default='admin')
    
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('confirmed', 'Connected')
    ], default='draft', string='Status')
    
    root_folder_id = fields.Char(string='Nextcloud Folder ID', readonly=False)
    root_folder_path = fields.Char(string='Actual Path', readonly=True)
    last_sync_token = fields.Char(string='Last Sync Token', readonly=True)

    root_maps = fields.One2many('nextcloud.root.map', 'client_id', string='Root Folders')

    def _get_connector(self):
        """Возвращает экземпляр оптимизированного NextcloudConnector"""
        self.ensure_one()
        return NextcloudConnector(self.url, self.username, self.password)

    def _get_full_url(self, path=None, file_id=None):
        """
        Универсальный метод для получения полного URL (согласно логике v.2.0):
        * Если есть file_id, использовать '/remote.php/dav/dav-oc-id/{file_id}'
        * Если есть path, использовать '/remote.php/dav/files/{login}/{path}'
        """
        self.ensure_one()
        base_url = self.url.rstrip('/')
        if file_id:
            return f"{base_url}/remote.php/dav/dav-oc-id/{file_id}"
        elif path is not None:
            return f"{base_url}/remote.php/dav/files/{self.username}/{path.lstrip('/')}"
        return f"{base_url}/remote.php/dav/"

    def set_root_folder_id_logic(self):
        """
        Logic for initializing the root folder.
        1. Local search for the root folder in the cloud root.
        2. If not found, perform a global search by ID.
        3. If ID is empty or folder not found, create a new root folder in the cloud root.
        """
        self.ensure_one()
        connector = self._get_connector()
        folder_info = None

        # 1. Local search in the cloud root
        folder_name = "Odoo Docs"
        _logger.info("Attempting to find root folder locally in cloud root: '%s'", folder_name)
        try:
            folder_info = connector.find_object(file_path=folder_name)
            if folder_info:
                _logger.info("Root folder found locally in cloud root: %s", folder_info)
        except Exception as e:
            _logger.warning("Local search for root folder in cloud root failed: %s", e)

        # 2. Global search by ID if local search yields no result
        if not folder_info and self.root_folder_id:
            try:
                _logger.info("Attempting to find root folder globally by ID: %s", self.root_folder_id)
                folder_info = connector.find_object_by_id(self.root_folder_id)

                if folder_info:
                    _logger.info("Root folder found globally: %s", folder_info)
            except Exception as e:
                _logger.warning("Global search for root folder by ID failed: %s", e)

        # 3. If ID is empty or folder not found, create a new root folder in the cloud root
        if not folder_info:
            _logger.info("Root folder not found. Creating new root folder: '%s'", folder_name)
            folder_info = connector.create_root_folder(folder_name)

        return folder_info

    def action_test_connection(self):
        """
        Проверка соединения и актуализация путей.
        """
        self.ensure_one()

        if self.root_folder_id:
            path = self._get_connector().get_path_by_direct_id(self.root_folder_id)
            if path:
                # Remove leading slash for consistency
                path = path.lstrip('/')
                self.write({'root_folder_path': path, 'state': 'confirmed'})
                _logger.info("Connection successful. Root folder path updated: %s", path)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload'
                }
            else:
                _logger.info("Direct ID access failed, falling back to name-based search.")

        # If no valid ID or direct access failed, fallback to text-based search or creation
        folder_info = self.set_root_folder_id_logic()
        if folder_info and folder_info.get('file_id'):
            self.write({
                'root_folder_id': str(folder_info['file_id']),
                'root_folder_path': folder_info['path'],
                'state': 'confirmed'
            })
            _logger.info("Root folder found or created: ID=%s, Path=%s", folder_info['file_id'], folder_info['path'])
        else:
            self.write({'state': 'draft'})
            raise UserError("Failed to initialize root folder in Nextcloud.")

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_edit_connection(self):
        """Сброс в черновик для редактирования параметров доступа"""
        self.ensure_one()
        self.write({'state': 'draft'})
        return True

    def action_reset_id(self):
        """Полный сброс привязки к папке"""
        self.ensure_one()
        self.write({
            'root_folder_id': False, 
            'root_folder_path': False, 
            'state': 'draft'
        })
        return True

# end of nextcloud/models/nextcloud_client.py