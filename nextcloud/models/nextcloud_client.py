# -*- File: nextcloud/models/nextcloud_client.py -*-

import requests
import xml.etree.ElementTree as ET
from odoo import models, fields, api
from odoo.exceptions import UserError
from urllib.parse import unquote
import logging

_logger = logging.getLogger(__name__)

class NextcloudClient(models.Model):
    _name = 'nextcloud.client'
    _description = 'Nextcloud Client Configuration'
    
    name = fields.Char(string='Config Name', required=True, default='Local Nextcloud')
    url = fields.Char(string='Base URL', required=True, default='http://localhost:8080')
    username = fields.Char(string='Username', required=True, default='admin')
    password = fields.Char(string='Password', required=True, default='admin')
    root_path = fields.Char(string='Target Folder ID or Link')
    
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Connected')], default='draft')
    root_folder_id = fields.Many2one(comodel_name='nextcloud.file', string='Main Folder', readonly=True)
    root_folder_path = fields.Char(related='root_folder_id.path', string='Actual Path', readonly=True)

    def _req(self, method, path, data=None, headers=None):
        clean_path = path if path.startswith('/') else f'/{path}'
        full_url = f"{self.url.rstrip('/')}{clean_path}"
        auth = (self.username, self.password)
        try:
            res = requests.request(method, full_url, auth=auth, data=data, headers=headers, timeout=20)
            return res
        except Exception as e:
            _logger.error("Nextcloud Request Error: %s", str(e))
            raise UserError(f"Ошибка запроса: {str(e)}")

    def action_test_connection(self):
        self.ensure_one()
        if not self.root_path:
            raise UserError("Укажите Target Folder ID или Link")
            
        raw_input = self.root_path.strip().rstrip('/')
        folder_id = raw_input.split('/')[-1] if not raw_input.isdigit() else raw_input

        # Используем только чтение (SEARCH/PROPFIND), никаких MOVE
        search_url = "/remote.php/dav/"
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
        <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
          <d:basicsearch>
            <d:select><d:prop><d:displayname/><oc:fileid/></d:prop></d:select>
            <d:from><d:scope><d:href>/files/{self.username}</d:href><d:depth>infinity</d:depth></d:scope></d:from>
            <d:where><d:eq><d:prop><oc:fileid/></d:prop><d:literal>{folder_id}</d:literal></d:eq></d:where>
          </d:basicsearch>
        </d:searchrequest>"""

        res = self._req('SEARCH', search_url, data=body.encode('utf-8'), headers={'Content-Type': 'text/xml'})
        
        if res.status_code not in [200, 207]:
            _logger.error("Nextcloud server returned %s", res.status_code)
            raise UserError(f"Сервер вернул ошибку {res.status_code}. Проверьте URL и доступы.")

        tree = ET.fromstring(res.content)
        ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
        node = tree.find('.//d:response', ns)
        
        if node is None:
            raise UserError(f"Папка с ID {folder_id} не найдена в Nextcloud.")

        href = unquote(node.find('.//d:href', ns).text)
        display_name = node.find('.//d:displayname', ns)
        name = display_name.text if display_name is not None and display_name.text else href.split('/')[-1]

        file_obj = self.env['nextcloud.file']
        root_file = file_obj.search([
            ('client_id', '=', self.id), ('file_id', '=', folder_id)
        ], limit=1)

        vals = {
            'name': name, 
            'path': href, 
            'file_type': 'dir', 
            'client_id': self.id, 
            'file_id': folder_id
        }

        # Принудительно отключаем MOVE логику при записи/создании
        if root_file:
            root_file.with_context(no_nextcloud_move=True).write(vals)
        else:
            root_file = file_obj.with_context(no_nextcloud_move=True).create(vals)
        
        self.write({
            'root_folder_id': root_file.id,
            'state': 'confirmed'
        })

        # Запускаем синхронизацию контента также с защитой от MOVE
        root_file.with_context(no_nextcloud_move=True)._sync_folder_contents()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Успех',
                'message': f'Соединение установлено. Папка "{name}" синхронизирована.',
                'sticky': False,
            }
        }

    def action_edit_connection(self):
        self.write({'state': 'draft'})
        return True

# -*- End of file nextcloud/models/nextcloud_client.py -*-