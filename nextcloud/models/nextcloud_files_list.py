from odoo import models, fields, api
from email.utils import parsedate_to_datetime
from urllib.parse import unquote

class NextcloudFile(models.Model):
    _name = 'nextcloud.file'
    _description = 'Nextcloud File'
    _order = 'file_type asc, name'

    name = fields.Char('File Name', readonly=True)
    path = fields.Char('Remote Path', readonly=True)
    file_type = fields.Selection([('file', 'File'), ('dir', 'Directory')], string='Type')
    size = fields.Float('Size (MB)', readonly=True, store=True)
    last_modified = fields.Datetime('Last Modified', readonly=True)
    
    # Ссылка на настройки, откуда пришел файл
    client_id = fields.Many2one('nextcloud.client', string='Storage')

    # Дополнительные метаданные
    etag = fields.Char('ETag', readonly=True)
    content_type = fields.Char('Content Type', readonly=True)
    file_id = fields.Char('File ID', readonly=True)
    owner = fields.Char('Owner', readonly=True)
    permissions = fields.Char('Permissions', readonly=True)
    extension = fields.Char('Extension', compute='_compute_extension', readonly=True)
    icon_html = fields.Html(string="Icon", compute='_compute_icon_html', readonly=True)

    # Поле для связи папка -> файлы
    parent_id = fields.Many2one('nextcloud.file', string='Parent Folder', ondelete='cascade', index=True)
    child_ids = fields.One2many('nextcloud.file', 'parent_id', string='Files inside')
    is_synced = fields.Boolean('Synced', default=False) # Флаг: заходили ли мы уже в эту папку

    @api.depends('path', 'client_id.url', 'client_id.username')
    def _compute_urls(self):
        for rec in self:
            rec.download_url = False
            rec.preview_url = False
            if not rec.client_id or not rec.client_id.url or not rec.path:
                continue
            base = rec.client_id.url.rstrip('/')
            username = getattr(rec.client_id, 'username', '') or ''
            path = rec.path
            if not path.startswith('/'):
                path = '/' + path
            # Формируем URL: <base><path>
            url = base + path
            rec.download_url = url if rec.file_type == 'file' else False
            if rec.file_type == 'dir':
                # Для директорий используем веб-интерфейс, извлекаем относительный путь
                relative_path = path.replace('/remote.php/dav/files/{}/'.format(username), '')
                rec.preview_url = "{}/apps/files/?dir={}".format(base, '/' + relative_path)
            else:
                # Для файлов открываем папку с файлом
                relative_path = path.replace('/remote.php/dav/files/{}/'.format(username), '')
                dirname = '/'.join(relative_path.split('/')[:-1])
                rec.preview_url = "{}/apps/files/?dir={}".format(base, '/' + dirname if dirname else '/')

    @api.depends('name')
    def _compute_extension(self):
        for rec in self:
            if rec.name and '.' in rec.name:
                rec.extension = rec.name.split('.')[-1].lower()
            else:
                rec.extension = False

    @api.depends('content_type', 'file_type', 'extension')
    def _compute_icon_html(self):
        for rec in self:
            # Цвета и классы по умолчанию
            icon_class = "fa-file-o"
            color = "#6c757d"  # Серый

            if rec.file_type == 'dir':
                icon_class = "fa-folder"
                color = "#ffc107"  # Золотистый
            elif rec.extension == 'pdf':
                icon_class = "fa-file-pdf-o"
                color = "#dc3545"  # Красный
            elif rec.extension in ['xls', 'xlsx']:
                icon_class = "fa-file-excel-o"
                color = "#198754"  # Зеленый
            elif rec.extension in ['doc', 'docx']:
                icon_class = "fa-file-word-o"
                color = "#0d6efd"  # Синий
            elif rec.extension in ['png', 'jpg', 'jpeg']:
                icon_class = "fa-file-image-o"
                color = "#fd7e14"  # Оранжевый
            elif rec.extension in ['zip', 'rar']:
                icon_class = "fa-file-archive-o"
                color = "#6f42c1"  # Фиолетовый

            # Генерируем HTML код иконки
            rec.icon_html = f'<i class="fa {icon_class} fa-lg" style="color: {color};"></i>'

    def action_download(self):
        self.ensure_one()
        if not self.download_url:
            return
        return {
            'type': 'ir.actions.act_url',
            'url': self.download_url,
            'target': 'new'
        }

    def action_preview(self):
        self.ensure_one()
        if not self.preview_url:
            return
        return {
            'type': 'ir.actions.act_url',
            'url': self.preview_url,
            'target': 'new'
        }

    def action_open_folder(self):
        self.ensure_one()
        
        if self.file_type == 'dir':
            # 1. Синхронизируем содержимое
            self._sync_folder_contents()
            
            # 2. Возвращаем действие открытия этого же списка, но с фильтром
            return {
                'name': self.name,
                'type': 'ir.actions.act_window',
                'res_model': 'nextcloud.file',
                'view_mode': 'list,form',
                'domain': [('parent_id', '=', self.id)],
                'context': {
                    'default_parent_id': self.id,
                    'default_client_id': self.client_id.id
                },
                'target': 'current', # Важно: открываем в том же окне
            }
        else:
            # Если это файл — открываем его форму (карточку), как обычно
            return {
                'name': self.name,
                'type': 'ir.actions.act_window',
                'res_model': 'nextcloud.file',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_create_folder_wizard(self):
        """Открывает окно для ввода имени новой папки"""
        return {
            'name': 'Создать новую папку',
            'type': 'ir.actions.act_window',
            'res_model': 'nextcloud.create.folder.wizard', # Создадим эту модель ниже
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_parent_id': self.env.context.get('default_parent_id'),
                'default_client_id': self.env.context.get('default_client_id'),
            }
        }

    def action_upload_file_wizard(self):
        """Открывает окно для выбора файла для загрузки"""
        return {
            'name': 'Загрузить файл в Nextcloud',
            'type': 'ir.actions.act_window',
            'res_model': 'nextcloud.upload.file.wizard', # И эту тоже
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_parent_id': self.env.context.get('default_parent_id'),
                'default_client_id': self.env.context.get('default_client_id'),
            }
        }

    def _sync_folder_contents(self):
        """ Метод для получения списка файлов конкретной папки """
        self.ensure_one()
        client = self.client_id._get_client() # Твой метод получения коннекта
        
        # Очищаем путь: декодируем %20 в пробелы, если они там есть
        target_path = unquote(self.path)
        
        # Убираем префикс, чтобы получить относительный путь
        username = self.client_id.username
        if target_path.startswith('/remote.php/dav/files/{}/'.format(username)):
            target_path = target_path.replace('/remote.php/dav/files/{}/'.format(username), '')
        
        # Для папок добавляем слеш в конце, если его нет
        if not target_path.endswith('/') and self.file_type == 'dir':
            target_path += '/'
        
        print(f"DEBUG: Try to list path: {target_path}")
        
        # Пытаемся получить список
        try:
            items = client.list(target_path, get_info=True)
        except Exception as e:
            # Если папка не найдена, возможно стоит попробовать убрать/добавить слеш в конце
            if target_path.endswith('/'):
                target_path = target_path.rstrip('/')
            else:
                target_path += '/'
            print(f"DEBUG: Retry with path: {target_path}")
            items = client.list(target_path, get_info=True)
        
        total_folder_size = 0.0
        
        for item in items:
            # Пропускаем саму папку (WebDAV возвращает текущую папку в списке)
            item_path = item.get('path', '')
            if item_path.rstrip('/') == target_path.rstrip('/'):
                continue
                
            # Считаем размер в байтах (WebDAV отдает размер файлов)
            file_size_bytes = int(item.get('size', 0) or 0)
            size_mb = file_size_bytes / 1024 / 1024
            
            # Плюсуем к общему размеру папки
            total_folder_size += size_mb
                
            # Полный путь для записи
            full_path = '/remote.php/dav/files/{}/{}'.format(username, item_path.lstrip('/'))
            
            vals = {
                'name': item_path.split('/')[-2] if item.get('isdir') else item_path.split('/')[-1],
                'path': full_path,
                'file_type': 'dir' if item.get('isdir') else 'file',
                'parent_id': self.id,
                'client_id': self.client_id.id,
                'size': size_mb,
                'last_modified': parsedate_to_datetime(item.get('modified')).replace(tzinfo=None) if item.get('modified') else False,
                'etag': item.get('etag'),
                'content_type': item.get('contenttype'),
                'file_id': item.get('fileid'),
            }
            
            # Ищем, есть ли уже такая запись, чтобы не дублировать
            existing = self.search([('path', '=', full_path), ('client_id', '=', self.client_id.id)], limit=1)
            if existing:
                existing.write(vals)
            else:
                self.create(vals)
        
        # В конце записываем накопленный размер в текущую папку
        self.write({'size': total_folder_size})
        
        # Помечаем папку как синхронизированную
        self.is_synced = True