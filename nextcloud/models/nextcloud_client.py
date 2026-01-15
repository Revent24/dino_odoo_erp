#
#  -*- File: nextcloud/models/nextcloud_client.py -*-
#
#
#  -*- File: nextcloud/models/nextcloud_client.py -*-
#

import requests
import xml.etree.ElementTree as ET
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from urllib.parse import unquote

_logger = logging.getLogger(__name__)

class NextcloudClient(models.Model):
    _name = 'nextcloud.client'
    _description = 'Nextcloud Client'

    name = fields.Char(string='Config Name', required=True, default='Local Nextcloud')
    url = fields.Char(string='Base URL', required=True, default='http://localhost:8080')
    username = fields.Char(string='Username', required=True, default='admin')
    password = fields.Char(string='Password', required=True, default='admin')
    root_path = fields.Char(string='Target Folder ID or Link')
    
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Connected')], default='draft')
    root_folder_id = fields.Many2one('nextcloud.file', string='Main Folder', readonly=True)
    root_folder_path = fields.Char(related='root_folder_id.path', string='Actual Path', readonly=True)

    def _req(self, method, path, data=None, headers=None):
        clean_path = path if path.startswith('/') else f'/{path}'
        full_url = f"{self.url.rstrip('/')}{clean_path}"
        auth = (self.username, self.password)
        try:
            res = requests.request(method, full_url, auth=auth, data=data, headers=headers, timeout=20)
            return res
        except Exception as e:
            raise UserError(f"Ошибка запроса: {str(e)}")

    def action_test_connection(self):
        self.ensure_one()
        raw_input = self.root_path.strip().rstrip('/')
        
        # Если это не просто число - берем хвост после последнего слеша
        if not raw_input.isdigit():
            folder_id = raw_input.split('/')[-1]
        else:
            folder_id = raw_input

        _logger.info("Using Folder ID: %s", folder_id)

        search_url = "/remote.php/dav/"
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
        <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
          <d:basicsearch>
            <d:select>
              <d:prop><d:displayname/><oc:fileid/></d:prop>
            </d:select>
            <d:from>
              <d:scope>
                <d:href>/files/{self.username}</d:href>
                <d:depth>infinity</d:depth>
              </d:scope>
            </d:from>
            <d:where>
              <d:eq>
                <d:prop><oc:fileid/></d:prop>
                <d:literal>{folder_id}</d:literal>
              </d:eq>
            </d:where>
          </d:basicsearch>
        </d:searchrequest>"""

        res = self._req('SEARCH', search_url, data=body.encode('utf-8'), headers={'Content-Type': 'text/xml'})
        if res.status_code not in [200, 207]:
            raise UserError(f"Сервер вернул ошибку {res.status_code}")

        tree = ET.fromstring(res.content)
        ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
        node = tree.find('.//d:response', ns)
        
        if node is None:
            raise UserError(f"Папка {folder_id} не найдена в Nextcloud.")

        href = unquote(node.find('.//d:href', ns).text)
        name = (node.find('.//d:displayname', ns).text or href.split('/')[-1])

        root_file = self.env['nextcloud.file'].search([
            ('client_id', '=', self.id), ('file_id', '=', folder_id)
        ], limit=1)

        vals = {'name': name, 'path': href, 'file_type': 'dir', 'client_id': self.id, 'file_id': folder_id}

        if root_file:
            root_file.write(vals)
        else:
            root_file = self.env['nextcloud.file'].create(vals)
        
        self.root_folder_id = root_file.id
        self.state = 'confirmed'
        self.invalidate_recordset(['root_folder_id', 'root_folder_path'])
        
        root_file._sync_folder_contents()
        return True

    def action_edit_connection(self):
        self.state = 'draft'
        return True

    def get_action_open_client(self):
        self.ensure_one()
        if self.root_folder_id:
            self.root_folder_id._sync_folder_contents()
        return {
            'name': 'Nextcloud Files',
            'type': 'ir.actions.act_window',
            'res_model': 'nextcloud.file',
            'view_mode': 'list,form',
            'domain': [('parent_id', '=', self.root_folder_id.id)],
            'context': {'default_client_id': self.id, 'default_parent_id': self.root_folder_id.id},
            'target': 'current',
        }

# End of file nextcloud/models/nextcloud_client.py# End of file nextcloud/models/nextcloud_client.py
