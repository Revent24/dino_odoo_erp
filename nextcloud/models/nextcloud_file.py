# -*- File: nextcloud/models/nextcloud_file.py -*-

import xml.etree.ElementTree as ET
from odoo import models, fields, api
from odoo.exceptions import UserError
from email.utils import parsedate_to_datetime
from urllib.parse import unquote, urlparse, quote
import logging
import os

from .nextcloud_api import NextcloudConnector

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
            # Синхронизируем корень перед открытием
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
            rec.path_readable = unquote(rec.path) if rec.path else ""

    def write(self, vals):
        if self.env.context.get('no_nextcloud_move') or 'name' not in vals:
            return super(NextcloudFile, self).write(vals)

        for rec in self:
            if not rec.path or not rec.client_id:
                continue

            new_name_raw = vals.get('name', '').strip()
            
            # ПРОВЕРКА: Если новое имя без расширения совпадает со старым без расширения
            # Или если новое имя (которое ты ввел) после обработки коннектором станет таким же
            # Мы просто отменяем переименование на сервере
            
            # Получаем текущее расширение
            orig_name = unquote(rec.path).rstrip('/').split('/')[-1]
            ext = orig_name.rpartition('.')[-1] if '.' in orig_name and rec.file_type != 'dir' else ''
            
            # Если ты ввел "test" вместо "test.md", мы сами добавим .md и сравним
            check_name = new_name_raw
            if ext and not check_name.lower().endswith(f".{ext.lower()}"):
                check_name = f"{check_name}.{ext}"
            
            if check_name == orig_name:
                # Имя по сути не поменялось, просто обновляем vals['name'] на полное и выходим
                vals['name'] = orig_name
                continue 

            # Если всё же имя другое — идем на сервер
            new_path, new_id = NextcloudConnector.rename_node(
                rec.client_id, 
                rec.path, 
                new_name_raw, 
                rec.file_type == 'dir'
            )
            
            if new_path:
                vals['path'] = new_path
                vals['name'] = unquote(new_path).rstrip('/').split('/')[-1]
                if new_id:
                    vals['file_id'] = new_id
            else:
                raise UserError(f"Не удалось переименовать '{rec.name}'")

        return super(NextcloudFile, self.with_context(no_nextcloud_move=True)).write(vals)
    
    def _get_clean_path(self, path_str):
        if not path_str: return ''
        return unquote(urlparse(path_str).path).strip('/')

    def _resolve_actual_path(self):
        """Проверка актуальности пути по ID (самозаживление связей)"""
        self.ensure_one()
        if not self.file_id or not self.client_id: 
            return self.path
        
        new_path = NextcloudConnector.get_path_by_id(self.client_id, self.file_id)
        if new_path and new_path != self.path:
            _logger.info("Путь для %s изменился в облаке. Обновляем: %s -> %s", self.name, self.path, new_path)
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
        """Основная логика синхронизации содержимого папки"""
        self.ensure_one()
        # Блокируем любые попытки MOVE во время чтения
        self = self.with_context(no_nextcloud_move=True)
        
        current_path = self._resolve_actual_path()
        headers = {'Depth': '1', 'Content-Type': 'application/xml'}
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:prop>
                <d:displayname/><d:getcontentlength/><oc:size/><d:getlastmodified/><d:resourcetype/><oc:fileid/>
            </d:prop>
        </d:propfind>"""
        
        res = self.client_id._req('PROPFIND', current_path, data=body.encode('utf-8'), headers=headers)
        if res.status_code not in [200, 207]: 
            _logger.warning("PROPFIND failed for %s: %s", current_path, res.status_code)
            return False
            
        try:
            tree = ET.fromstring(res.content)
            norm_current = self._get_clean_path(current_path).strip('/')
            
            for resp in tree.findall('.//{*}response'):
                href_node = resp.find('.//{*}href')
                if href_node is None: continue
                
                href_text = href_node.text
                norm_href = self._get_clean_path(href_text).strip('/')
                
                # Пропускаем саму текущую папку
                if norm_href == norm_current: continue
                
                f_id, mod_date, f_size = False, False, 0.0
                prop_node = resp.find('.//{*}prop')
                if prop_node is not None:
                    for child in prop_node:
                        tag = child.tag.split('}')[-1]
                        if tag == 'fileid': f_id = child.text
                        if tag == 'getlastmodified' and child.text:
                            try: mod_date = parsedate_to_datetime(child.text).replace(tzinfo=None)
                            except: pass
                        if tag == 'size' and child.text:
                            f_size = round(float(child.text) / (1024*1024), 2)
                        elif tag == 'getcontentlength' and child.text and f_size == 0:
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
                    existing.write(vals)
                else:
                    self.create(vals)

            return True
        except Exception as e:
            _logger.error("Ошибка при разборе XML синхронизации: %s", str(e))
            return False

    def action_sync_current_folder(self):
        folder = self if self.file_type == 'dir' else self.parent_id
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