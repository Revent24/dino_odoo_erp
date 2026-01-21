# -*- File: nextcloud/models/nextcloud_client.py -*-

import requests
import xml.etree.ElementTree as ET
from odoo import models, fields, api
from odoo.exceptions import UserError
from urllib.parse import unquote
import logging

# Проверь путь! Если api.py в папке tools, то: from ..tools.nextcloud_api import NextcloudConnector
# Если в папке models, оставляем так:
from ..tools.nextcloud_api import NextcloudConnector

_logger = logging.getLogger(__name__)

class NextcloudClient(models.Model):
    _name = 'nextcloud.client'
    _description = 'Nextcloud Client Configuration'
    
    name = fields.Char(string='Config Name', required=True, default='Local Nextcloud')
    url = fields.Char(string='Base URL', required=True, default='http://localhost:8080')
    username = fields.Char(string='Username', required=True, default='admin')
    password = fields.Char(string='Password', required=True, default='admin')
    root_path = fields.Char(string='Root Path', readonly=True)
    
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Connected')], default='draft')
    root_folder_id = fields.Char(string='Nextcloud Folder ID', readonly=False)
    root_folder_path = fields.Char(string='Actual Path', readonly=True)

    root_maps = fields.One2many('nextcloud.root.map', 'client_id', string='Root Folders')

    def _req(self, method, path, data=None, headers=None):
        """Базовый метод для всех запросов к Nextcloud"""
        # Гарантируем один слэш между url и path
        clean_path = '/' + path.lstrip('/')
        full_url = f"{self.url.rstrip('/')}{clean_path}"
        auth = (self.username, self.password)
        try:
            res = requests.request(method, full_url, auth=auth, data=data, headers=headers, timeout=20)
            return res
        except Exception as e:
            _logger.error("Nextcloud Request Error: %s", str(e))
            raise UserError(f"Ошибка связи с сервером: {str(e)}")

    def action_reset_id(self):
        self.write({'root_folder_id': False, 'root_folder_path': False, 'state': 'draft'})

    def action_test_connection(self):
        self.ensure_one()
        _logger.info("NC_DEBUG: Тестирование соединения (ID: %s)", self.root_folder_id)
        
        if not self.root_folder_id:
            # ТЕСТ НА ПУСТОМ ID: создаем папку по умолчанию
            path, ids = NextcloudConnector.ensure_path_v2(self, ['Odoo Docs'])
            if ids:
                self.write({
                    'root_folder_id': ids[-1].lstrip('0'),
                    'root_folder_path': path,
                    'state': 'confirmed'
                })
            else:
                raise UserError("Не удалось создать корневую папку автоматически.")
        else:
            # ПОИСК ПО УКАЗАННОМУ ID
            info = NextcloudConnector.get_info_by_id(self, self.root_folder_id)
            if info and info.get('path'):
                self.write({
                    'root_folder_path': info['path'],
                    'state': 'confirmed'
                })
            else:
                self.write({'state': 'draft'})
                raise UserError(f"Папка с ID {self.root_folder_id} не найдена на сервере.")

        # Возвращаем действие для обновления интерфейса (reload)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Успех',
                'message': 'Данные синхронизированы',
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_edit_connection(self):
        """Возвращает состояние в draft для редактирования настроек"""
        self.ensure_one()
        self.state = 'draft'
        return True
# -*- End of file nextcloud/models/nextcloud_client.py -*-