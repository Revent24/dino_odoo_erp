# -*- File: nextcloud/mixins/nextcloud_project_mixin.py -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..tools.nextcloud_api import NextcloudConnector

_logger = logging.getLogger(__name__)

class NextcloudProjectMixin(models.AbstractModel):
    _name = 'nextcloud.file.project.mixin'
    _inherit = 'nextcloud.file.base.mixin'

    def _get_nc_client(self):
        # Исправлено: ищем без user_id
        return self.env['nextcloud.client'].search([('state', '=', 'confirmed')], limit=1)

    def _get_month_name(self, month_index):
        months = {1: 'січень', 2: 'лютий', 3: 'березень', 4: 'квітень', 5: 'травень', 
                  6: 'червень', 7: 'липень', 8: 'серпень', 9: 'вересень', 
                  10: 'жовтень', 11: 'листопад', 12: 'грудень'}
        return months.get(month_index, '')

    def _get_nc_folder_parts(self):
        """Возвращает список имен папок: [Категория, Год, Месяц, Проект]"""
        d = self.date or fields.Date.today()
        return [
            self.project_category_id.name,  # Категория
            f"{d.year} рік",  # Год
            f"{d.year}-{d.month:02d} {self._get_month_name(d.month)}",  # Месяц
            f"{d.strftime('%Y-%m-%d')} {self.name}"  # Проект
        ]

    def _get_or_create_root_mapping(self, client):
        category = self.project_category_id
        if not category:
            raise UserError("У проекта не выбрана категория!")

        _logger.info("NC_DEBUG: Checking mapping for category: %s", category.name)

        # 1. Ищем существующий маппинг для этой категории
        mapping = self.env['nextcloud.root.map'].search([
            ('model_id.model', '=', 'dino.project.category'),
            ('res_id', '=', category.id),
            ('client_id', '=', client.id)
        ], limit=1)

        nc_path = False
        
        # 2. Если маппинг есть, проверяем актуальность пути по ID
        if mapping and mapping.folder_id and mapping.folder_id.file_id:
            # Пытаемся получить актуальный путь из NC по сохраненному ID
            nc_path = NextcloudConnector.get_path_by_id(client, mapping.folder_id.file_id)
            if nc_path:
                # Если путь в NC изменился (переименовали папку), обновляем в базе
                if mapping.folder_id.path != nc_path:
                    mapping.folder_id.with_context(no_nextcloud_move=True).write({'path': nc_path})
        
        # 3. Если по ID ничего не нашли, ищем по имени (как раньше)
        if not nc_path:
            # Синхронизация с NC: ищем или создаем папку по имени категории
            base_root = client.root_folder_path
            cat_path, cat_nc_id = NextcloudConnector.ensure_path(client, [category.name], base_root)

            # Создаем/обновляем запись папки в Odoo
            file_rec = self.env['nextcloud.file'].search([
                ('client_id', '=', client.id),
                ('file_id', '=', cat_nc_id)
            ], limit=1)

            file_vals = {
                'name': category.name,
                'path': cat_path,
                'file_id': cat_nc_id,
                'file_type': 'dir',
                'client_id': client.id,
            }

            if file_rec:
                file_rec.with_context(no_nextcloud_move=True).write(file_vals)
            else:
                file_rec = self.env['nextcloud.file'].with_context(no_nextcloud_move=True).create(file_vals)

            # Создаем или обновляем маппинг
            map_vals = {
                'client_id': client.id,
                'model_id': self.env['ir.model']._get('dino.project.category').id,
                'res_id': category.id,
                'folder_name': category.name,
                'folder_id': file_rec.id,
            }

            if mapping:
                mapping.write(map_vals)
            else:
                mapping = self.env['nextcloud.root.map'].create(map_vals)

            return file_rec

        return mapping.folder_id

    def action_ensure_nc_folder(self):
        self.ensure_one()
        client = self._get_nc_client()
        import json

        # 1. Получаем корень из маппинга категорий
        mapping = self.env['nextcloud.root.map'].search([
            ('model_id.model', '=', 'dino.project.category'),
            ('res_id', '=', self.project_category_id.id),
            ('client_id', '=', client.id)
        ], limit=1)
        
        if not mapping or not mapping.folder_id or not mapping.folder_id.file_id:
            # Если маппинга еще нет, сначала создаем/находим корень
            category_folder = self._get_or_create_root_mapping(client)
            mapping = self.env['nextcloud.root.map'].search([
                ('model_id.model', '=', 'dino.project.category'),
                ('res_id', '=', self.project_category_id.id),
                ('client_id', '=', client.id)
            ], limit=1)

        # 2. Формируем желаемые имена [Категория, Год, Месяц, Проект]
        parts = self._get_nc_folder_parts() 
        
        # 3. Инициализируем или загружаем ID
        # Если поле пустое, создаем список, где первый элемент - ID корня
        if not self.nc_path_ids and mapping and mapping.folder_id.file_id:
            current_ids = json.dumps([mapping.folder_id.file_id])
        else:
            current_ids = self.nc_path_ids

        # 4. Вызываем API v2
        final_path, updated_ids = NextcloudConnector.ensure_path_v2(
            client, 
            parts, 
            path_ids_json=current_ids,
            base_path=client.root_folder_path or "Odoo Docs"  # Относительный путь от корня пользователя
        )

        if updated_ids:
            self.write({
                'nc_path_ids': json.dumps(updated_ids),
            })
            
            # Обновляем запись в UI (nextcloud.file)
            project_folder_id = updated_ids[-1]
            file_rec = self.env['nextcloud.file'].search([('file_id', '=', project_folder_id)], limit=1)
            
            vals = {
                'name': parts[-1],
                'path': final_path,
                'file_id': project_folder_id,
                'res_model': self._name,
                'res_id': self.id,
            }
            
            if file_rec:
                file_rec.with_context(no_nextcloud_move=True).write(vals)
            else:
                file_rec = self.env['nextcloud.file'].create(vals)
                
            self.write({'nc_folder_id': file_rec.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._update_category_mapping()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in ['project_category_id', 'name', 'date']):
            for rec in self:
                rec._update_category_mapping()
        return res

    def _update_category_mapping(self):
        """
        Синхронизирует папку категории. 
        Если папка есть — обновляет её метаданные в NC по ID.
        """
        self.ensure_one()
        client = self._get_nc_client()
        if not client or not self.project_category_id:
            return

        # Получаем/Создаем маппинг через наш бронебойный метод
        folder_rec = self._get_or_create_root_mapping(client)
        
        # Если имя категории изменилось, переименовываем папку в Nextcloud по ID
        if folder_rec.name != self.project_category_id.name:
            _logger.info("NC_DEBUG: Переименование категории по ID %s -> %s", 
                         folder_rec.file_id, self.project_category_id.name)
            
            new_path = NextcloudConnector.rename_node(
                client, 
                folder_rec.path, 
                self.project_category_id.name, 
                is_dir=True
            )
            
            if new_path:
                folder_rec.with_context(no_nextcloud_move=True).write({
                    'name': self.project_category_id.name,
                    'path': new_path
                })

# End of file nextcloud/mixins/nextcloud_project_mixin.py