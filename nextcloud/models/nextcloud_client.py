from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from email.utils import parsedate_to_datetime
from urllib.parse import unquote

try:
    from webdav3.client import Client
except Exception as e:
    Client = None
    logging.getLogger(__name__).warning("webdav3 not available: %s", e)

class NextcloudClient(models.Model):
    _name = 'nextcloud.client'
    _description = 'Nextcloud Client for WebDAV'

    name = fields.Char(string='Config Name', required=True, default='Local Nextcloud')
    url = fields.Char(string='Base URL', required=True, default='http://localhost:8080')
    username = fields.Char(string='Username', required=True, default='admin')
    password = fields.Char(string='Password', required=True, default='admin')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Connected'),
        ('error', 'Error')
    ], default='draft')

    # Поле для выбора стартовой папки
    root_folder_id = fields.Many2one(
        'nextcloud.file', 
        string='Main Folder',
        domain="[('client_id', '=', id), ('file_type', '=', 'dir')]"
    )

    def _get_client(self):
        """Инициализация клиента WebDAV"""
        options = {
            'webdav_hostname': self.url,
            'webdav_login':    self.username,
            'webdav_password': self.password,
            'webdav_root':     f'/remote.php/dav/files/{self.username}/'
        }
        return Client(options)

    def action_test_connection(self):
        """Тестирует соединение с Nextcloud"""
        try:
            client = self._get_client()
            client.list('/')  # Простой тест соединения
            self.state = 'confirmed'
            # После успешного соединения загружаем папки для выбора
            self.action_fetch_folders()
            self.env.cr.commit()  # Сохраняем изменения перед открытием формы
            return [
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'Connection to Nextcloud successful',
                        'type': 'success'
                    }
                },
                {
                    'type': 'ir.actions.act_window',
                    'name': 'Nextcloud Clients',
                    'res_model': 'nextcloud.client',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            ]
        except Exception as e:
            self.state = 'error'
            return [
                {
                   'type': 'ir.actions.act_window',
                    'name': 'Nextcloud Clients',
                    'res_model': 'nextcloud.client',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'current',
                },
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Connection failed: {str(e)}',
                        'type': 'danger'
                        }
                }

            ]

    def create_folder(self, remote_path):
        """Создает папку (включая вложенные)"""
        client = self._get_client()
        try:
            # mkdir создает путь рекурсивно
            if not client.check(remote_path):
                client.mkdir(remote_path)
            return True
        except Exception as e:
            raise UserError(f"Ошибка WebDAV: {str(e)}")

    def action_fetch_folders(self):
        """Метод для загрузки только структуры папок, чтобы пользователь мог выбрать одну"""
        self.ensure_one()
        # Синхронизируем только если Main Folder не выбрана
        if not self.root_folder_id:
            self.action_sync_files() 
        return True

    def list_files(self, path='/'):
        """Возвращает нормальный список имен файлов вместо сырого XML"""
        client = self._get_client()
        return client.list(path)

    def upload_binary(self, binary_data, remote_filename):
        """Загрузка файла напрямую из Odoo (base64) в облако"""
        import io
        client = self._get_client()
        file_obj = io.BytesIO(binary_data)
        return client.upload_from_fileobj(file_obj, remote_filename)

    @api.model
    def create(self, vals):
        if self.search_count([]) > 0:
            raise UserError("Only one Nextcloud client configuration is allowed.")
        return super().create(vals)

    def write(self, vals):
        return super().write(vals)

    @api.model
    def get_action_open_client(self):
        """Ensure a single Nextcloud client exists and return an act_window action opening it.

        Algorithm:
        - Try to resolve external id `dino_erp.nextcloud_client_default` via env.ref.
        - If it maps to an existing record -> use it.
        - If it maps to a non-existing record -> create a new record and update the external id.
        - If external id not present -> use the first existing record if any, or create one and register it.
        """
        _logger = logging.getLogger(__name__)
        Imd = self.env['ir.model.data']

        # Try to resolve XML id safely
        rec = None
        try:
            ref = self.env.ref('dino_erp.nextcloud_client_default', raise_if_not_found=False)
            if ref and ref.id:
                candidate = self.browse(ref.id)
                if candidate.exists():
                    rec = candidate
                    _logger.info('Using existing nextcloud.client from ir.model.data: id=%s', rec.id)
                else:
                    _logger.info('ir.model.data points to missing nextcloud.client id=%s; will create new', ref.id)
        except Exception:
            _logger.warning('Failed to resolve env.ref for dino_erp.nextcloud_client_default', exc_info=True)

        # If no record resolved via XML id, search for any existing record
        if not rec:
            records = self.search([], order='id')
            if records:
                rec = records[0]
                if len(records) > 1:
                    _logger.info('Found multiple nextcloud.client records; keeping id=%s', rec.id)
                    (records - rec).unlink()
                _logger.info('Using existing nextcloud.client id=%s', rec.id)
            else:
                _logger.info('No nextcloud.client found; creating default one')
                rec = self.create({
                    'name': 'Default Nextcloud Connection',
                    'url': 'http://localhost:8080',
                    'username': 'admin',
                    'password': 'admin',
                    'state': 'draft',
                })

        # Ensure ir.model.data maps to the keeper record
        found = Imd.search([('module', '=', 'dino_erp'), ('name', '=', 'nextcloud_client_default')], limit=1)
        if found:
            if found.res_id != rec.id or found.model != 'nextcloud.client':
                _logger.info('Updating ir.model.data nextcloud_client_default -> %s', rec.id)
                found.write({'res_id': rec.id, 'model': 'nextcloud.client'})
        else:
            _logger.info('Creating ir.model.data mapping for nextcloud_client_default -> %s', rec.id)
            Imd.create({'module': 'dino_erp', 'name': 'nextcloud_client_default', 'model': 'nextcloud.client', 'res_id': rec.id, 'noupdate': True})

        return {
            'type': 'ir.actions.act_window',
            'name': 'Nextcloud Clients',
            'res_model': 'nextcloud.client',
            'res_id': rec.id,
            'view_mode': 'form',
            'target': 'current',
            'view_id': self.env.ref('dino_erp.view_nextcloud_client_form').id,
        }

    def action_sync_files(self):
        _logger = logging.getLogger(__name__)
        for rec in self:
            client = rec._get_client()
            
            # 1. Определяем относительный путь для WebDAV
            sync_path = '/'
            parent_id = False
            
            if rec.root_folder_id:
                parent_id = rec.root_folder_id.id
                # Очищаем путь от системного префикса Nextcloud
                prefix = f'/remote.php/dav/files/{rec.username}/'
                sync_path = rec.root_folder_id.path.replace(prefix, '').rstrip('/')
                if not sync_path: sync_path = '/'

            _logger.info(f"Syncing path: {sync_path}")

            try:
                # get_info=True вернет fileid, etag и прочее
                files_info = client.list(sync_path, get_info=True)
            except Exception as e:
                _logger.error(f"WebDAV Error: {e}")
                continue

            existing_files = self.env['nextcloud.file'].search([
                ('client_id', '=', rec.id),
                ('parent_id', '=', parent_id)
            ])
            
            current_paths = set()
            for info in files_info:
                item_path = info.get('path', '')
                
                # Пропускаем саму папку поиска
                if item_path.strip('/') == sync_path.strip('/'):
                    continue
                    
                # Формируем системный путь для БД
                if item_path.startswith('/remote.php/dav/files/'):
                    full_path = item_path
                else:
                    full_path = f'/remote.php/dav/files/{rec.username}/{item_path.lstrip("/")}' if item_path else f'/remote.php/dav/files/{rec.username}/'
                current_paths.add(full_path)
                
                # Определяем имя файла/папки
                if item_path.startswith('/remote.php/dav/files/'):
                    relative_path = item_path.replace(f'/remote.php/dav/files/{rec.username}/', '', 1).rstrip('/')
                    name = relative_path.split('/')[-1] if relative_path else ''
                else:
                    name = item_path.rstrip('/').split('/')[-1] if item_path else ''
                
                vals = {
                    'name': unquote(name),
                    'path': full_path,
                    'file_type': 'dir' if info.get('isdir') else 'file',
                    'size': float(info.get('size') or 0) / 1024 / 1024,
                    'last_modified': parsedate_to_datetime(info.get('modified')).replace(tzinfo=None) if info.get('modified') else False,
                    'etag': info.get('etag'),
                    'file_id': info.get('fileid'),
                    'client_id': rec.id,
                    'parent_id': parent_id, # ПРИВЯЗКА К ВЫБРАННОЙ ПАПКЕ
                }

                existing = existing_files.filtered(lambda f: f.path == full_path)
                if existing:
                    existing.write(vals)
                else:
                    self.env['nextcloud.file'].create(vals)

            # Удаляем то, чего больше нет в этой папке
            existing_files.filtered(lambda f: f.path not in current_paths).unlink()
        return True