# -*- File: nextcloud/models/nextcloud_client.py -*-

import requests
import xml.etree.ElementTree as ET
from odoo import models, fields, api
from odoo.exceptions import UserError
from urllib.parse import unquote
import logging

# Проверь путь! Если api.py в папке tools, то: from ..tools.nextcloud_api import NextcloudConnector
# Если в папке models, оставляем так:
from .nextcloud_api import NextcloudConnector

_logger = logging.getLogger(__name__)

class NextcloudClient(models.Model):
    _name = 'nextcloud.client'
    _description = 'Nextcloud Client Configuration'
    
    name = fields.Char(string='Config Name', required=True, default='Local Nextcloud')
    url = fields.Char(string='Base URL', required=True, default='http://localhost:8080')
    username = fields.Char(string='Username', required=True, default='admin')
    password = fields.Char(string='Password', required=True, default='admin')
    root_path = fields.Char(string='Target Folder ID or Link', help="ID папки из Nextcloud (Settings -> Copy Link)")
    
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Connected')], default='draft')
    root_folder_id = fields.Many2one(comodel_name='nextcloud.file', string='Main Folder', readonly=True)
    root_folder_path = fields.Char(related='root_folder_id.path', string='Actual Path', readonly=True)

    def _req(self, method, path, data=None, headers=None):
        """Базовый метод для всех запросов к Nextcloud"""
        # Убираем возможные дубли слэшей
        clean_path = path if path.startswith('/') else f'/{path}'
        full_url = f"{self.url.rstrip('/')}{clean_path}"
        auth = (self.username, self.password)
        try:
            res = requests.request(method, full_url, auth=auth, data=data, headers=headers, timeout=20)
            return res
        except Exception as e:
            _logger.error("Nextcloud Request Error: %s", str(e))
            raise UserError(f"Ошибка связи с сервером: {str(e)}")

    def action_test_connection(self):
        self.ensure_one()
        if not self.root_path:
            raise UserError("Укажите Target Folder ID или Link")
            
        raw_input = self.root_path.strip().rstrip('/')
        folder_id = raw_input.split('/')[-1] if not raw_input.isdigit() and '/' in raw_input else raw_input

        # Только проверка пути, без глубокого сканирования содержимого
        href = NextcloudConnector.get_path_by_id(self, folder_id)
        if not href:
            raise UserError(f"Папка с ID {folder_id} не найдена.")

        decoded_path = unquote(href).rstrip('/')
        name = decoded_path.split('/')[-1] or f"Root_{folder_id[:8]}"

        vals = {
            'name': name, 
            'path': href, 
            'file_type': 'dir', 
            'client_id': self.id, 
            'file_id': folder_id
        }

        file_obj = self.env['nextcloud.file']
        root_file = file_obj.search([('client_id', '=', self.id), ('file_id', '=', folder_id)], limit=1)

        if root_file:
            root_file.with_context(no_nextcloud_move=True).write(vals)
        else:
            root_file = file_obj.with_context(no_nextcloud_move=True).create(vals)
        
        self.write({
            'root_folder_id': root_file.id,
            'state': 'confirmed'
        })

        # Возвращаем простое обновление страницы без уведомлений и задержек
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_edit_connection(self):
        self.write({'state': 'draft'})
        return True

# -*- End of file nextcloud/models/nextcloud_client.py -*-