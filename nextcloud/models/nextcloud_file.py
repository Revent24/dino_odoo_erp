#
#  -*- File: nextcloud/models/nextcloud_file.py -*-
# 

import requests
import xml.etree.ElementTree as ET
from odoo import models, fields, api
from odoo.exceptions import UserError
from email.utils import parsedate_to_datetime
from urllib.parse import unquote, urlparse, quote
import logging

_logger = logging.getLogger(__name__)

class NextcloudFile(models.Model):
    _name = 'nextcloud.file'
    _description = 'Nextcloud File'
    _order = 'file_type asc, name'

    name = fields.Char('File Name') 
    file_id = fields.Char('ID (Server)', readonly=True, index=True)
    path = fields.Char('Remote Path', readonly=True)
    file_type = fields.Selection([('file', 'File'), ('dir', 'Directory')], string='Type', readonly=True)
    size = fields.Float('Size (MB)', readonly=True)
    last_modified = fields.Datetime('Last Modified', readonly=True)
    
    client_id = fields.Many2one('nextcloud.client', string='Storage', readonly=True)
    parent_id = fields.Many2one('nextcloud.file', string='Parent Folder', ondelete='cascade')
    child_ids = fields.One2many('nextcloud.file', 'parent_id', string='Files')
    
    icon_html = fields.Html(string=" ", compute='_compute_icon_html')
    debug_info = fields.Text('Debug Info')

    def name_get(self):
        return [(rec.id, rec.name or rec.path or 'Unknown') for rec in self]

    @api.depends('file_type')
    def _compute_icon_html(self):
        for rec in self:
            icon = "fa-folder" if rec.file_type == 'dir' else "fa-file-o"
            color = "#ffc107" if rec.file_type == 'dir' else "#6c757d"
            rec.icon_html = f'<i class="fa {icon}" style="color: {color};"></i>'

    def write(self, vals):
        for rec in self:
            if not rec.file_id:
                continue
            old_path = rec.path
            new_name = vals.get('name', rec.name)
            if 'parent_id' in vals:
                new_parent = self.browse(vals['parent_id'])
                new_path = f"{new_parent.path.rstrip('/')}/{quote(new_name)}"
            elif 'name' in vals:
                path_parts = old_path.rstrip('/').split('/')
                path_parts[-1] = quote(new_name)
                new_path = "/".join(path_parts)
                if rec.file_type == 'dir': new_path += '/'
            else:
                new_path = old_path

            if old_path != new_path:
                res = rec.client_id._req('MOVE', old_path, headers={'Destination': new_path})
                if res.status_code not in [201, 204]:
                    raise UserError(f"Ошибка перемещения: {res.status_code}")
                vals['path'] = new_path
        return super(NextcloudFile, self).write(vals)

    def _get_clean_path(self, path_str):
        if not path_str: return ''
        return unquote(urlparse(path_str).path).strip('/')

    def _resolve_actual_path(self):
        self.ensure_one()
        if not self.file_id or not self.client_id: return self.path
        search_url = "/remote.php/dav/"
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
        <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
          <d:basicsearch>
            <d:select><d:prop><d:displayname/><oc:fileid/></d:prop></d:select>
            <d:from><d:scope><d:href>/files/{self.client_id.username}</d:href><d:depth>infinity</d:depth></d:scope></d:from>
            <d:where><d:eq><d:prop><oc:fileid/></d:prop><d:literal>{self.file_id}</d:literal></d:eq></d:where>
          </d:basicsearch>
        </d:searchrequest>"""
        res = self.client_id._req('SEARCH', search_url, data=body.encode('utf-8'), headers={'Content-Type': 'text/xml'})
        if res.status_code in [200, 207]:
            tree = ET.fromstring(res.content)
            resp = tree.find('.//{*}response')
            if resp is not None:
                href = resp.find('.//{*}href')
                if href is not None:
                    new_path = href.text
                    if new_path != self.path:
                        self.env.cr.execute("UPDATE nextcloud_file SET path=%s WHERE id=%s", (new_path, self.id))
                    return new_path
        return self.path

    def action_open_folder(self):
        self.ensure_one()
        if self.file_type == 'dir':
            self._sync_folder_contents()
            return {
                'name': self.name, 'type': 'ir.actions.act_window', 'res_model': 'nextcloud.file',
                'view_mode': 'list,form', 'domain': [('parent_id', '=', self.id)],
                'context': {'default_parent_id': self.id, 'default_client_id': self.client_id.id},
                'target': 'current',
            }
        return self.action_view_form()

    def action_view_form(self):
        self.ensure_one()
        return {
            'name': f"Инфо: {self.name}", 'type': 'ir.actions.act_window', 'res_model': 'nextcloud.file',
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }

    def _sync_folder_contents(self):
        self.ensure_one()
        current_path = self._resolve_actual_path()
        headers = {'Depth': '1', 'Content-Type': 'application/xml'}
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:prop><d:displayname/><d:getcontentlength/><d:getlastmodified/><d:resourcetype/><oc:fileid/></d:prop>
        </d:propfind>"""
        res = self.client_id._req('PROPFIND', current_path, data=body.encode('utf-8'), headers=headers)
        if res.status_code not in [200, 207]: return False

        try:
            tree = ET.fromstring(res.content)
            norm_current = self._get_clean_path(current_path)
            found_ids = []

            for resp in tree.findall('.//{*}response'):
                href_node = resp.find('.//{*}href')
                if href_node is None: continue
                href_raw = href_node.text
                norm_href = self._get_clean_path(href_raw)
                if norm_href == norm_current: continue

                f_id = False
                prop_node = resp.find('.//{*}prop')
                if prop_node is not None:
                    for child in prop_node:
                        if 'fileid' in child.tag:
                            f_id = child.text
                            break

                is_dir = resp.find('.//{*}collection') is not None
                size_node = resp.find('.//{*}getcontentlength')
                mod_node = resp.find('.//{*}getlastmodified')
                name = unquote(norm_href.split('/')[-1])
                
                vals = {
                    'name': name, 'path': href_raw, 'file_id': f_id, 'file_type': 'dir' if is_dir else 'file',
                    'client_id': self.client_id.id, 'parent_id': self.id,
                    'size': (int(size_node.text or 0) / 1024 / 1024) if size_node is not None and size_node.text else 0,
                    'last_modified': parsedate_to_datetime(mod_node.text).replace(tzinfo=None) if mod_node is not None and mod_node.text else False,
                    'debug_info': ET.tostring(resp, encoding='unicode')
                }

                domain = [('client_id', '=', self.client_id.id)]
                if f_id:
                    domain.append(('file_id', '=', f_id))
                    found_ids.append(f_id)
                else:
                    domain.append(('path', '=', href_raw))

                existing = self.search(domain, limit=1)
                if existing: super(NextcloudFile, existing).write(vals)
                else: self.create(vals)

            if found_ids:
                self.search([('parent_id', '=', self.id), ('file_id', 'not in', found_ids), ('file_id', '!=', False)]).unlink()
            return True
        except Exception as e:
            _logger.error("Sync Error: %s", str(e))
            return False

    def action_create_folder_wizard(self):
        self.ensure_one()
        return {
            'name': 'Создать папку', 'type': 'ir.actions.act_window', 'res_model': 'nextcloud.wizard.create.folder',
            'view_mode': 'form', 'target': 'new', 'context': {'default_parent_file_id': self.id}
        }

    def action_upload_file_wizard(self):
        self.ensure_one()
        return {
            'name': 'Загрузить файл', 'type': 'ir.actions.act_window', 'res_model': 'nextcloud.wizard.upload.file',
            'view_mode': 'form', 'target': 'new', 'context': {'default_parent_file_id': self.id}
        }

# End of file nextcloud/models/nextcloud_file.py