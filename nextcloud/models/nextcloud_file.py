# -*- File: nextcloud/models/nextcloud_file.py -*-

import xml.etree.ElementTree as ET
from odoo import models, fields, api
from odoo.exceptions import UserError
from email.utils import parsedate_to_datetime
from urllib.parse import unquote, urlparse, quote
import logging
import os

from ..tools.nextcloud_api import NextcloudConnector

_logger = logging.getLogger(__name__)

class NextcloudFile(models.Model):
    _name = 'nextcloud.file'
    _description = 'Nextcloud File'
    _order = 'file_type asc, name'

    name = fields.Char('File Name') 
    file_id = fields.Char('ID (Server)', readonly=True, index=True)
    parent_file_id = fields.Char('Parent ID (Server)', readonly=True)
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
        if not client or not client.root_folder_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'nextcloud.client',
                'view_mode': 'form',
                'target': 'current',
            }

        connector = client._get_connector()
        c_id = str(connector._clean_id(client.root_folder_id))
        root_node = self.search([('client_id', '=', client.id), ('file_id', '=', c_id)], limit=1)

        if not root_node:
            _logger.info("NC_DEBUG: Создаем корневую запись для ID %s", c_id)
            root_node = self.create({
                'name': 'Odoo Docs',
                'file_id': c_id,
                'path': client.root_folder_path or f'/remote.php/dav/files/{client.username}/Odoo Docs',
                'file_type': 'dir',
                'client_id': client.id
            })

        root_node.with_context(no_nextcloud_move=True)._sync_folder_contents()
        self.env.cr.commit()

        return {
            'name': 'Nextcloud Files',
            'type': 'ir.actions.act_window',
            'res_model': 'nextcloud.file',
            'view_mode': 'list,form',
            'domain': [('parent_id', '=', root_node.id)],
            'context': {'default_parent_id': root_node.id, 'default_client_id': client.id},
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

    @api.depends('name', 'parent_id', 'parent_id.path_readable')
    def _compute_path_readable(self):
        """
        Хлебные крошки: расчет читаемого пути на основе иерархии parent_id.
        """
        for rec in self:
            if rec.parent_id:
                rec.path_readable = f"{rec.parent_id.path_readable} / {rec.name}"
            else:
                rec.path_readable = rec.name or ""

    def write(self, vals):
        """
        Обновление записи файла. Если изменяется имя, выполняется переименование в Nextcloud.
        С защитой расширений файлов.
        """
        if 'name' in vals and not self._context.get('no_nextcloud_move'):
            for record in self:
                if record.client_id and record.file_id:
                    new_name = vals['name']
                    # Защита расширения
                    if record.file_type == 'file':
                        old_ext = os.path.splitext(record.name)[1] if record.name else ""
                        new_ext = os.path.splitext(new_name)[1]
                        if old_ext and old_ext != new_ext:
                            new_name = os.path.splitext(new_name)[0] + old_ext
                            vals['name'] = new_name

                    try:
                        connector = record.client_id._get_connector()
                        username = record.client_id.username
                        prefix = f"/remote.php/dav/files/{username}/"
                        
                        # Получаем текущий путь из record.path или через API
                        current_path = record.path or record._resolve_actual_path()
                        if not current_path:
                            continue
                            
                        clean_old_path = current_path.replace(prefix, "").strip("/")
                        parent_dir = '/'.join(clean_old_path.split('/')[:-1])
                        new_clean_path = f"{parent_dir}/{new_name}".strip("/")
                        
                        connector.move_object(record.file_id, new_clean_path)
                        
                        # Обновляем путь в записи
                        data = connector.get_object_data(file_id=record.file_id)
                        if data:
                             vals['path'] = data['href']
                    except Exception as e:
                        _logger.error("Ошибка переименования в NC: %s", e)
                        raise UserError(f"Ошибка Nextcloud: {e}")
        return super(NextcloudFile, self).write(vals)

    def _resolve_actual_path(self):
        """Проверка актуальности пути по ID (v.2.0)"""
        self.ensure_one()
        if not self.file_id or not self.client_id: 
            return self.path
        
        try:
            connector = self.client_id._get_connector()
            data = connector.get_object_data(file_id=self.file_id)
            if data and data['href'] != self.path:
                _logger.info("Путь для %s изменился. Обновляем: %s -> %s", self.name, self.path, data['href'])
                self.with_context(no_nextcloud_move=True).write({'path': data['href']})
                return data['href']
            return data['href'] if data else self.path
        except Exception:
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
        """
        Синхронизация содержимого папки с сервером Nextcloud (v.2.0).
        """
        self.ensure_one()
        client_rec = self.client_id
        if not client_rec:
            return

        connector = client_rec._get_connector()

        # 1. Актуализируем путь текущей папки
        actual_path = self._resolve_actual_path()
        username = client_rec.username
        prefix = f"/remote.php/dav/files/{username}"
        clean_path = actual_path.replace(prefix, "").strip("/")

        # 2. Получаем содержимое через PROPFIND Depth: 1
        headers = {'Depth': '1', 'Content-Type': 'application/xml'}
        body = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
            '  <d:prop>'
            '    <d:displayname/>'
            '    <d:resourcetype/>'
            '    <oc:fileid/>'
            '    <d:getcontentlength/>'
            '    <d:getlastmodified/>'
            '  </d:prop>'
            '</d:propfind>'
        )
        
        response = connector._do_request('PROPFIND', path=clean_path, headers=headers, data=body)
        if response.status_code not in (200, 207):
            _logger.error("Sync failed for path %s: %s", clean_path, response.status_code)
            return

        from lxml import etree
        root = etree.fromstring(response.content)
        ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}

        responses = root.xpath('//d:response', namespaces=ns)
        # Пропускаем саму папку (первый элемент)
        for resp in responses[1:]:
            href = resp.xpath('.//d:href/text()', namespaces=ns)[0]
            name_list = resp.xpath('.//d:displayname/text()', namespaces=ns)
            name = name_list[0] if name_list else unquote(href.rstrip('/').split('/')[-1])
            f_id_list = resp.xpath('.//oc:fileid/text()', namespaces=ns)
            f_id = f_id_list[0] if f_id_list else None
            
            res_type = resp.find('.//d:resourcetype', ns)
            is_dir = res_type is not None and res_type.find('.//d:collection', ns) is not None
            
            size_list = resp.xpath('.//d:getcontentlength/text()', namespaces=ns)
            size = float(size_list[0]) / (1024 * 1024) if size_list else 0.0
            
            mod_list = resp.xpath('.//d:getlastmodified/text()', namespaces=ns)
            last_mod = parsedate_to_datetime(mod_list[0]).replace(tzinfo=None) if mod_list else False

            if not f_id:
                continue

            file_vals = {
                'name': name,
                'file_id': str(f_id),
                'parent_file_id': self.file_id,
                'path': href,
                'file_type': 'dir' if is_dir else 'file',
                'size': size,
                'last_modified': last_mod,
                'client_id': client_rec.id,
                'parent_id': self.id,
            }

            existing = self.env['nextcloud.file'].search([
                ('client_id', '=', client_rec.id),
                ('file_id', '=', str(f_id))
            ], limit=1)

            if existing:
                existing.with_context(no_nextcloud_move=True).write(file_vals)
            else:
                self.env['nextcloud.file'].with_context(no_nextcloud_move=True).create(file_vals)

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