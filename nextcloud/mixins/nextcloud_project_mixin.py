# -*- File: nextcloud/mixins/nextcloud_project_mixin.py -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)

class NextcloudProjectMixin(models.AbstractModel):
    _name = 'nextcloud.file.project.mixin'
    _inherit = 'nextcloud.file.base.mixin'

    nc_id_chain = fields.Char("NC ID Chain", copy=False)

    @api.depends('nc_id_chain', 'date', 'name', 'project_category_id')
    def _compute_nc_path_readable(self):
        """Отображает иерархию папок в читаемом виде (v.2.0)"""
        for rec in self:
            parts = rec._get_project_path_parts()
            rec.nc_path_readable = " / ".join(parts) if parts else ""

    nc_path_readable = fields.Char("NC Path", compute='_compute_nc_path_readable')

    def _get_month_name(self, month_index):
        months = {1: 'січень', 2: 'лютий', 3: 'березень', 4: 'квітень', 5: 'травень', 
                  6: 'червень', 7: 'липень', 8: 'серпень', 9: 'вересень', 
                  10: 'жовтень', 11: 'листопад', 12: 'грудень'}
        return months.get(month_index, '')

    def _get_project_path_parts(self):
        """
        Возвращает список частей пути (v.2.0): [Категория, Год, Месяц, Проект]
        """
        self.ensure_one()
        d = self.date or fields.Date.today()
        category_name = self.project_category_id.name or 'Без категории'
        return [
            category_name,
            f"{d.year} рік",
            f"{d.year}-{d.month:02d} {self._get_month_name(d.month)}",
            f"{d.strftime('%Y-%m-%d')} {self.name} [{self.id}]"
        ]

    def action_ensure_nc_folder(self):
        """
        Создает/актуализирует полную иерархию папок в Nextcloud по ID (v.2.0).
        Автоматически переименовывает или перемещает папки, если они изменились в Odoo.
        """
        self.ensure_one()
        client = self._get_nc_client()
        if not client or not client.root_folder_id:
            _logger.warning("NC Build: Client not ready.")
            return

        connector = client._get_connector()
        root_id = int(connector._clean_id(client.root_folder_id))
        parts = self._get_project_path_parts()
        
        try:
            chain = json.loads(self.nc_id_chain or "{}")
        except:
            chain = {}

        # 1. Сначала актуализируем путь к корню (Odoo Docs)
        root_info = connector.get_object_data(file_id=root_id)
        if not root_info:
            # Если корень пропал - пробуем перенастроить
            client.set_root_folder_id()
            root_id = int(connector._clean_id(client.root_folder_id))
            root_info = connector.get_object_data(file_id=root_id)
        
        if not root_info:
            raise UserError(_("Не удалось найти корневую папку в Nextcloud."))

        current_parent_id = root_id
        current_parent_path = root_info['path'] # Актуальный путь из сервера

        new_chain = {}
        segment_keys = ['cat_id', 'year_id', 'month_id', 'project_id']
        
        last_file_record = self.env['nextcloud.file'].search([
            ('client_id', '=', client.id), 
            ('file_id', '=', str(root_id))
        ], limit=1)

        for i, name in enumerate(parts):
            key = segment_keys[i]
            seg_id = chain.get(key)
            expected_path = f"{current_parent_path}/{name}".strip("/")
            
            actual_info = None
            
            # Для общих папок (Категория, Год, Месяц) сначала ищем по имени в родителе
            if i < 3:
                child_id = connector.find_in_folder(current_parent_id, name)
                if child_id:
                    seg_id = child_id
                    actual_info = connector.get_object_data(file_id=seg_id)
                else:
                    # Если по имени нет - обеспечиваем создание
                    seg_id = connector.ensure_path_step(current_parent_id, name)
                    actual_info = connector.get_object_data(file_id=seg_id)
            else:
                # Для папки самого ПРОЕКТА - ищем по ID из цепочки
                if seg_id:
                    actual_info = connector.find_by_id(seg_id, path_scope=current_parent_path)
                    if not actual_info:
                        actual_info = connector.find_by_id(seg_id)
                    
                    if actual_info:
                        actual_path = actual_info['path'].strip("/")
                        if actual_path != expected_path:
                            _logger.info("Moving project folder ID %s: %s -> %s", seg_id, actual_path, expected_path)
                            try:
                                connector.move_object(seg_id, expected_path)
                                actual_info = connector.get_object_data(path=expected_path)
                            except Exception as e:
                                _logger.error("Failed to move project: %s", e)

                if not actual_info:
                    # Если по ID не нашли - ищем по имени в текущем родителе
                    child_id = connector.find_in_folder(current_parent_id, name)
                    if child_id:
                        seg_id = child_id
                    else:
                        seg_id = connector.ensure_path_step(current_parent_id, name)
                    actual_info = connector.get_object_data(file_id=seg_id)
            
            # СИНХРОНИЗАЦИЯ локальной таблицы
            if actual_info:
                file_rec = self.env['nextcloud.file'].search([
                    ('client_id', '=', client.id),
                    ('file_id', '=', str(seg_id))
                ], limit=1)
                
                vals = {
                    'name': name, # Всегда используем имя из Odoo
                    'file_id': str(seg_id),
                    'path': actual_info['href'],
                    'file_type': 'dir',
                    'client_id': client.id,
                    'parent_id': last_file_record.id if last_file_record else False,
                }
                
                if not file_rec:
                    file_rec = self.env['nextcloud.file'].create(vals)
                else:
                    file_rec.with_context(no_nextcloud_move=True).write(vals)
                
                last_file_record = file_rec

            new_chain[key] = seg_id
            current_parent_id = seg_id
            current_parent_path = actual_info['path'] if actual_info else expected_path

        # Финализация
        self.with_context(no_nextcloud_move=True).write({
            'nc_file_id': new_chain.get('project_id'),
            'nc_path': actual_info.get('href') if actual_info else False,
            'nc_id_chain': json.dumps(new_chain),
            'nc_folder_id': last_file_record.id if last_file_record else False
        })


    def write(self, vals):
        """
        При изменении значимых полей (имя, дата, категория) 
        запускаем выравнивание структуры в Nextcloud.
        """
        res = super(NextcloudProjectMixin, self).write(vals)
        
        # Если изменились поля, влияющие на путь, и мы не в режиме подавления перемещения
        trigger_fields = ['date', 'name', 'project_category_id']
        if any(f in vals for f in trigger_fields) and not self._context.get('no_nextcloud_move'):
            for rec in self:
                # Запускаем универсальный метод обеспечения структуры
                # Он найдет все папки по ID и переименует/переместит их если нужно
                try:
                    rec.action_ensure_nc_folder()
                except Exception as e:
                    _logger.error("Failed to sync NC folder on write: %s", e)
        return res

# End of file nextcloud/mixins/nextcloud_project_mixin.py