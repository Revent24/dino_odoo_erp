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

    def set_root_folder_id(self):
        """
        ГЛАВНАЯ ЛОГИКА (согласно задаче):
        1. Если есть ID — актуализируем по нему через SEARCH (самый надежный способ).
        2. Если ID нет или папка удалена — создаем 'Odoo Docs' и фиксируем новый ID.
        """
        self.ensure_one()
        connector = self._get_connector()
        folder_info = None

        # 1. Попытка найти по ID (Logic v.2.0)
        if self.root_folder_id:
            try:
                # Всегда ищем по ИД (двухэтапный поиск: локально потом глобально)
                # Для корня локальная область - это корень пользователя
                _logger.info("Syncing root folder by ID: %s", self.root_folder_id)
                folder_info = connector.find_by_id(self.root_folder_id)
                
                if folder_info:
                    _logger.info("Found root folder info: %s", folder_info)
            except Exception as e:
                _logger.warning("Failed to find root folder by ID %s: %s", self.root_folder_id, e)

        # 2. Если по ID не нашли — ищем/создаем по имени в корне
        if not folder_info:
            folder_name = "Odoo Docs"
            _logger.info("Folder not found by ID. Searching by name '%s' in root...", folder_name)
            try:
                folder_info = connector.get_object_data(path=folder_name)
                if not folder_info:
                    _logger.info("Creating new folder: %s", folder_name)
                    connector._do_request('MKCOL', path=folder_name)
                    folder_info = connector.get_object_data(path=folder_name)
            except Exception as e:
                _logger.error("Failed to create/find folder by name: %s", e)

        # 3. Сохраняем актуальный ID
        if folder_info and folder_info.get('file_id'):
            self.root_folder_id = str(folder_info['file_id'])
            _logger.info("Root folder established: %s (ID: %s)", folder_info.get('name'), self.root_folder_id)
        else:
            _logger.error("Failed to establish root folder.")

        # 3. Обновление данных
        if folder_info:
            self.write({
                'root_folder_id': str(folder_info['file_id']),
                'root_folder_path': folder_info['href'],
                'state': 'confirmed'
            })
            _logger.info("Root folder set: ID=%s, Path=%s", folder_info['file_id'], folder_info['href'])
        else:
            self.write({'state': 'draft'})
            raise UserError("Не удалось инициализировать корневую папку в Nextcloud.")

    def action_test_connection(self):
        """
        Кнопка проверки соединения и актуализации путей.
        Использует логику v.2.0: поиск преимущественно по ID.
        """
        self.ensure_one()
        self.set_root_folder_id()
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