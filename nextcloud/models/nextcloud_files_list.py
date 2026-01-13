from odoo import models, fields, api

class NextcloudFile(models.Model):
    _name = 'nextcloud.file'
    _description = 'Nextcloud File'

    name = fields.Char('File Name', readonly=True)
    path = fields.Char('Remote Path', readonly=True)
    file_type = fields.Selection([('file', 'File'), ('dir', 'Directory')], string='Type')
    size = fields.Float('Size (MB)', readonly=True)
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