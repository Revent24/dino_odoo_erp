# -*- File: nextcloud/models/nextcloud_file.py -*-

import xml.etree.ElementTree as ET
from odoo import models, fields, api
from odoo.exceptions import UserError
from email.utils import parsedate_to_datetime
from urllib.parse import unquote, urlparse, quote
import logging
import os

_logger = logging.getLogger(__name__)

class NextcloudFile(models.Model):
    _name = 'nextcloud.file'
    _description = 'Nextcloud File'
    _order = 'file_type asc, name'

    name = fields.Char('File Name') 
    file_id = fields.Char('ID (Server)', readonly=True, index=True)
    path = fields.Char('Remote Path', readonly=True)
    path_readable = fields.Char('Путь', compute='_compute_path_readable')
    file_type = fields.Selection([('file', 'File'), ('dir', 'Directory')], string='Type', readonly=True)
    size = fields.Float('Size (MB)', readonly=True)
    last_modified = fields.Datetime('Last Modified', readonly=True)
    
    client_id = fields.Many2one(comodel_name='nextcloud.client', string='Storage', readonly=True)
    parent_id = fields.Many2one(comodel_name='nextcloud.file', string='Parent Folder', ondelete='cascade')
    child_ids = fields.One2many('nextcloud.file', 'parent_id', string='Files')
    
    icon_html = fields.Html(string=" ", compute='_compute_icon_html')
    debug_info = fields.Text('Debug Info')

    @api.model
    def action_main_menu_open(self):
        client = self.env['nextcloud.client'].search([], limit=1)
        if not client:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'nextcloud.client',
                'view_mode': 'form',
                'target': 'current',
            }
        
        if client.state == 'confirmed' and client.root_folder_id:
            client.root_folder_id.with_context(no_nextcloud_move=True)._sync_folder_contents()
            return {
                'name': client.root_folder_id.name,
                'type': 'ir.actions.act_window',
                'res_model': 'nextcloud.file',
                'view_mode': 'list,form',
                'domain': [('parent_id', '=', client.root_folder_id.id)],
                'context': {
                    'default_parent_id': client.root_folder_id.id,
                    'default_client_id': client.id
                },
                'target': 'current',
            }
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'nextcloud.client',
            'res_id': client.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def name_get(self):
        return [(rec.id, rec.name or rec.path or 'Unknown') for rec in self]

    @api.depends('file_type')
    def _compute_icon_html(self):
        for rec in self:
            icon = "fa-folder" if rec.file_type == 'dir' else "fa-file-o"
            color = "#ffc107" if rec.file_type == 'dir' else "#6c757d"
            rec.icon_html = f'<i class="fa {icon}" style="color: {color}; font-size: 1.4rem; vertical-align: middle;"></i>'

    @api.depends('path')
    def _compute_path_readable(self):
        for rec in self:
            if rec.path:
                # unquote превращает %d0%a1%d1%96%d1%87%d0%b5%d0%bd%d1%8c в "Січень"
                rec.path_readable = unquote(rec.path)
            else:
                rec.path_readable = ""

    def write(self, vals):
        # Если это фоновая синхронизация или имя не меняется — не трогаем сервер
        if self.env.context.get('no_nextcloud_move') or 'name' not in vals:
            return super(NextcloudFile, self).write(vals)

        for rec in self:
            if not rec.path or not rec.client_id:
                continue

            new_name = vals.get('name', '').strip()
            
            # ЖЕСТКАЯ ЗАЩИТА РАСШИРЕНИЯ ДЛЯ ФАЙЛОВ
            if rec.file_type == 'file':
                # 1. Достаем расширение из текущего пути (справа от последней точки)
                # unquote на случай, если в пути есть %2E вместо точки
                current_path_decoded = unquote(rec.path)
                _, dot, extension = current_path_decoded.rpartition('.')
                
                if dot == '.':
                    ext_with_dot = dot + extension # получили ".md", ".pdf" и т.д.
                    
                    # 2. Отрезаем всё лишнее от того, что ввел Степан
                    # Если Степан ввел "Отчет.doc", а файл был ".pdf", мы уберем ".doc"
                    user_base_name, user_dot, _ = new_name.rpartition('.')
                    clean_name = user_base_name if user_dot == '.' else new_name
                    
                    # 3. Собираем итоговое имя
                    new_name = f"{clean_name}{ext_with_dot}"
                    vals['name'] = new_name
                    _logger.info("LOCK EXTENSION: %s -> %s (using ext %s)", vals.get('name'), new_name, ext_with_dot)

            # 4. Формируем путь для MOVE
            path_segments = rec.path.rstrip('/').split('/')
            path_segments[-1] = quote(new_name)
            new_path = '/'.join(path_segments)
            if rec.file_type == 'dir':
                new_path += '/'

            if rec.path == new_path:
                continue

            # 5. Команда MOVE на сервер
            dest_url = f"{rec.client_id.url.rstrip('/')}{new_path}"
            _logger.info("MOVE REQUEST: %s TO %s", rec.path, new_path)
            
            res = rec.client_id._req('MOVE', rec.path, headers={
                'Destination': dest_url,
                'Overwrite': 'F'
            })

            if res.status_code in [201, 204]:
                vals['path'] = new_path
                _logger.info("MOVE SUCCESS")
            else:
                _logger.error("MOVE FAILED: %s", res.status_code)
                raise UserError(f"Ошибка Nextcloud {res.status_code}: не удалось переименовать.")

        return super(NextcloudFile, self.with_context(no_nextcloud_move=True)).write(vals)

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
            self.with_context(no_nextcloud_move=True)._sync_folder_contents()
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
        self = self.with_context(no_nextcloud_move=True)
        
        current_path = self._resolve_actual_path()
        headers = {'Depth': '1', 'Content-Type': 'application/xml'}
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:prop><d:displayname/><d:getcontentlength/><oc:size/><d:getlastmodified/><d:resourcetype/><oc:fileid/></d:prop>
        </d:propfind>"""
        
        res = self.client_id._req('PROPFIND', current_path, data=body.encode('utf-8'), headers=headers)
        if res.status_code not in [200, 207]: 
            _logger.warning("PROPFIND failed for %s: %s", current_path, res.status_code)
            return False
            
        try:
            tree = ET.fromstring(res.content)
            norm_current = self._get_clean_path(current_path).strip('/')
            found_ids = []
            
            for resp in tree.findall('.//{*}response'):
                href_node = resp.find('.//{*}href')
                if href_node is None: continue
                
                href_text = href_node.text
                norm_href = self._get_clean_path(href_text).strip('/')
                if norm_href == norm_current: continue
                
                f_id = False
                mod_date = False
                f_size = 0.0
                prop_node = resp.find('.//{*}prop')
                if prop_node is not None:
                    for child in prop_node:
                        if 'fileid' in child.tag: f_id = child.text
                        if 'getlastmodified' in child.tag and child.text:
                            try:
                                mod_date = parsedate_to_datetime(child.text).replace(tzinfo=None)
                            except: pass
                        if 'size' in child.tag and child.text:
                            f_size = round(float(child.text) / (1024*1024), 2)

                is_dir = resp.find('.//{*}collection') is not None
                name = unquote(norm_href.split('/')[-1])
                if not name and is_dir:
                    parts = norm_href.split('/')
                    name = unquote(parts[-2]) if len(parts) > 1 else 'Folder'
                
                vals = {
                    'name': name, 'path': href_text, 'file_id': f_id, 'file_type': 'dir' if is_dir else 'file',
                    'client_id': self.client_id.id, 'parent_id': self.id,
                    'last_modified': mod_date, 'size': f_size
                }
                
                domain = [('client_id', '=', self.client_id.id), ('file_id', '=', f_id)] if f_id else [('path', '=', href_text)]
                existing = self.search(domain, limit=1)
                
                if existing:
                    existing.write({
                        'name': name, 
                        'last_modified': mod_date, 
                        'size': f_size,
                        'path': href_text
                    })
                else:
                    self.create(vals)
                if f_id: found_ids.append(f_id)

            return True
        except Exception as e:
            _logger.error("Sync Error: %s", str(e))
            return False

    def action_sync_current_folder(self):
        folder = self
        if self and self.file_type != 'dir':
            folder = self.parent_id
        
        if not folder:
            active_id = self.env.context.get('active_id') or self.env.context.get('default_parent_id')
            folder = self.browse(active_id) if active_id else False

        if folder and folder.exists():
            folder.with_context(no_nextcloud_move=True)._sync_folder_contents()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_create_folder_wizard(self):
        active_id = self.id or self.env.context.get('active_id') or self.env.context.get('default_parent_id')
        return {
            'name': 'Создать папку', 'type': 'ir.actions.act_window', 'res_model': 'nextcloud.wizard.create.folder',
            'view_mode': 'form', 'target': 'new', 'context': {'default_parent_file_id': active_id}
        }

    def action_upload_file_wizard(self):
        active_id = self.id or self.env.context.get('active_id') or self.env.context.get('default_parent_id')
        return {
            'name': 'Загрузить файл', 'type': 'ir.actions.act_window', 'res_model': 'nextcloud.wizard.upload.file',
            'view_mode': 'form', 'target': 'new', 'context': {'default_parent_file_id': active_id}
        }

# -*- End of file nextcloud/models/nextcloud_file.py -*-