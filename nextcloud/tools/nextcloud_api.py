# -*- File: nextcloud/tools/nextcloud_api.py -*-
import logging
import requests
import os
from lxml import etree
from urllib.parse import unquote
from email.utils import parsedate_to_datetime
from .nextcloud_xml_utils import get_propfind_body, get_search_body, parse_node_data

_logger = logging.getLogger(__name__)

class NextcloudConnector:
    def __init__(self, url, login, password):
        """
        Инициализация соединения с Nextcloud.
        """
        self.url = url.rstrip('/')
        self.auth = (login, password)

    def _clean_id(self, raw_id):
        """Очищает File-ID до чистого целого числа (согласно nc_info.md)"""
        if not raw_id:
            return None
        try:
            # Если это строка вида 00000063oczn5...
            clean_str = str(raw_id).split('oc')[0]
            return int(clean_str)
        except (ValueError, IndexError):
            return raw_id

    def _do_request(self, method, path=None, file_id=None, headers=None, data=None):
        """
        Универсальный метод для выполнения запросов к Nextcloud API.
        """
        if file_id:
            # Очищаем ID перед использованием в спец-эндпоинте
            c_id = self._clean_id(file_id)
            request_path = f"/remote.php/dav/dav-oc-id/{c_id}"
        elif path is not None:
            username = self.auth[0]
            # Экранируем путь для URL (важно для кириллицы и пробелов)
            from urllib.parse import quote
            safe_path = quote(path.lstrip('/'))
            request_path = f"/remote.php/dav/files/{username}/{safe_path}"
        else:
            # For methods like SEARCH, we use the base endpoint
            request_path = "/remote.php/dav/"

        url = self.url.rstrip('/') + request_path
        _logger.info("NC_REQUEST: %s %s", method, url)

        # Кодируем тело в UTF-8 если это строка, чтобы избежать UnicodeEncodeError (latin-1)
        if isinstance(data, str):
            data = data.encode('utf-8')

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            auth=self.auth,
            timeout=20
        )
        return response

    def _get_info_from_response(self, response_node, ns):
        """Парсит <d:response> и возвращает dict с метаданными"""
        href_raw = response_node.find('d:href', ns).text
        href = unquote(href_raw)
        
        # Очищаем href от префиксов (могут быть разные в зависимости от эндпоинта)
        path = href
        username = self.auth[0]
        prefixes = [
            f"/remote.php/dav/files/{username}",
            "/remote.php/dav/dav-oc-id"
        ]
        
        for prefix in prefixes:
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        
        path = path.strip('/')
        
        props = response_node.find('.//d:prop', ns)
        f_id_elem = props.find('oc:fileid', ns)
        name_elem = props.find('d:displayname', ns)
        res_type = props.find('d:resourcetype', ns)
        is_folder = res_type is not None and res_type.find('.//d:collection', ns) is not None

        return {
            'file_id': int(f_id_elem.text) if f_id_elem is not None else None,
            'href': href,
            'name': name_elem.text if name_elem is not None else os.path.basename(path),
            'path': path,
            'is_folder': is_folder
        }

    def _find_object(self, file_id=None, parent_id=None, name=None):
        """
        Универсальная функция для поиска объекта в Nextcloud.
        - Если указан file_id, выполняется поиск по ID через метод SEARCH.
        - Если указан parent_id и name, выполняется поиск по имени внутри родительской папки.
        Возвращает словарь с данными объекта или None, если объект не найден.
        """
        if file_id:
            return self.find_by_id(file_id)

        if parent_id and name:
            parent_info = self.get_object_data(file_id=parent_id)
            if not parent_info:
                return None

            headers = {'Depth': '1', 'Content-Type': 'application/xml; charset=utf-8'}
            body = (
                '<?xml version="1.0" encoding="utf-8" ?>'
                '<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
                '<d:prop><d:displayname/></d:prop>'
                '</d:propfind>'
            )

            response = self._do_request('PROPFIND', path=parent_info['path'], headers=headers, data=body)
            if response.status_code not in (200, 207):
                return None

            try:
                root = etree.fromstring(response.content)
                ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
                for resp in root.findall('.//d:response', ns):
                    name_elem = resp.find('.//d:displayname', ns)
                    if name_elem is not None and name_elem.text == name:
                        return self._get_info_from_response(resp, ns)
            except Exception as e:
                _logger.error("Error parsing PROPFIND response: %s", e)
                return None

        return None

    def find_by_id(self, file_id):
        """
        Ищет объект по File-ID через метод SEARCH.
        """
        headers = {'Content-Type': 'application/xml; charset=utf-8'}
        body = get_search_body(file_id)

        response = self._do_request('SEARCH', headers=headers, data=body)
        if response.status_code not in (200, 207):
            return None

        try:
            return parse_node_data(response.content)
        except ValueError as e:
            _logger.error("Error parsing SEARCH response: %s", e)
            return None

    def find_object_by_id(self, file_id):
        """
        Низкоуровневая функция для поиска объекта по ID через SEARCH.
        """
        _logger.info("Starting find_object_by_id with file_id: %s", file_id)
        headers = {'Content-Type': 'application/xml; charset=utf-8'}

        # Очистка file_id перед использованием
        clean_file_id = self._clean_id(file_id)
        _logger.debug("Cleaned file_id: %s", clean_file_id)

        body = get_search_body(clean_file_id)

        # Логирование сформированного XML для отладки
        _logger.debug("SEARCH request body: %s", body)

        response = self._do_request('SEARCH', headers=headers, data=body)
        _logger.info("SEARCH response status: %s", response.status_code)

        if response.status_code not in (200, 207):
            _logger.error("SEARCH request failed with status: %s", response.status_code)
            return None

        try:
            result = parse_node_data(response.content)
            _logger.info("SEARCH response parsed successfully: %s", result)
            return result
        except ValueError as e:
            _logger.error("Error parsing SEARCH response: %s", e)
            return None

    def get_object_data(self, path=None, file_id=None):
        """
        Выполняет запрос PROPFIND с заголовком {'Depth': '0'}.
        Возвращает словарь с данными: file_id, href, name, is_folder, path.
        """
        if file_id and not path:
            return self.find_object(file_id=file_id)

        headers = {'Depth': '0', 'Content-Type': 'application/xml; charset=utf-8'}
        body = get_propfind_body()

        response = self._do_request('PROPFIND', path=path, headers=headers, data=body)
        if response.status_code not in (200, 207):
            return None

        try:
            return parse_node_data(response.content)
        except ValueError as e:
            _logger.error("Error parsing PROPFIND response: %s", e)
            return None

    def ensure_path_step(self, parent_id, segment_name):
        """
        Обеспечивает наличие папки и возвращает её ID.
        Оптимизировано для использования универсальных методов.
        """
        _logger.info("Ensuring segment '%s' in parent ID %s", segment_name, parent_id)

        # Используем универсальный метод для поиска объекта по имени в родительской папке
        child_info = self.find_object_by_name_in_parent(parent_id, segment_name)

        if not child_info:
            parent_info = self.find_by_id(parent_id)
            if not parent_info:
                raise ValueError(f"Parent folder {parent_id} not found on server.")

            # Создаем новую папку
            new_folder_path = f"{parent_info['path']}/{segment_name}"
            self.create_folder(new_folder_path)
            child_info = self.find_object_by_name_in_parent(parent_id, segment_name)

        return child_info['file_id'] if child_info else None

    def create_folder(self, path):
        """
        Создает новую папку по указанному пути, если она не существует.
        """
        _logger.info("Starting create_folder with path: %s", path)

        # Проверяем, существует ли папка
        folder_info = self.get_object_data(path=path)
        if folder_info:
            _logger.info("Folder already exists: %s", path)
            return folder_info

        # Если папка не существует, создаем её
        response = self._do_request('MKCOL', path=path)
        _logger.info("MKCOL response status: %s for path: %s", response.status_code, path)

        if response.status_code == 201:
            _logger.info("Folder created successfully: %s", path)
            return self.get_object_data(path=path)
        elif response.status_code == 405:
            _logger.warning("Folder already exists (MKCOL returned 405): %s", path)
            return self.get_object_data(path=path)
        else:
            _logger.error("Failed to create folder: %s, Status: %s", path, response.status_code)
            return None

    def find_object(self, file_id=None, file_path=None):
        """
        Реализация двухшаговой логики поиска объекта:
        1. Оптимистичный поиск по пути (PROPFIND).
        2. Поиск-восстановление по ID (SEARCH).
        """
        _logger.info("Starting find_object with file_id: %s, file_path: %s", file_id, file_path)

        if file_path:
            # Шаг 1: Оптимистичный поиск по пути
            _logger.info("Attempting optimistic search by file_path: %s", file_path)
            object_data = self.get_object_data(path=file_path)
            if object_data:
                _logger.info("Object found by file_path: %s", object_data)
                if object_data.get('file_id') == file_id:
                    return object_data

        if file_id:
            # Шаг 2: Поиск-восстановление по ID
            _logger.info("Attempting recovery search by file_id: %s", file_id)
            result = self.find_by_id(file_id)
            if result:
                _logger.info("Object found by file_id: %s", result)
            else:
                _logger.warning("Object not found by file_id: %s", file_id)
            return result

        _logger.warning("find_object could not find object with file_id: %s and file_path: %s", file_id, file_path)
        return None

    def find_object_by_name_in_parent(self, parent_id, child_name):
        """
        Низкоуровневая функция для поиска объекта по имени внутри родительской папки.
        Используется для ensure_path_step.
        """
        return self._find_object(parent_id=parent_id, name=child_name)

    def set_root_folder(self, root_folder_name="Odoo Docs"):
        """
        Устанавливает корневую папку. Если она отсутствует, создаёт новую.
        """
        _logger.info("Starting set_root_folder with root_folder_name: %s", root_folder_name)

        root_folder = self.find_object(file_id=self.root_folder_id, file_path=self.root_folder_path)
        if root_folder:
            _logger.info("Root folder found: %s", root_folder)
        else:
            _logger.info("Root folder not found. Creating new root folder: %s", root_folder_name)
            self.create_folder(root_folder_name)
            root_folder = self.find_object_by_name_in_parent(parent_id=None, child_name=root_folder_name)

            if not root_folder:
                _logger.error("Failed to create or find root folder: %s", root_folder_name)
                raise ValueError("Не удалось создать или найти корневую папку.")

            self.root_folder_id = root_folder['file_id']
            self.root_folder_path = root_folder['path']

        _logger.info("Root folder set successfully: %s", root_folder)
        return root_folder

    def update_root_folder_path(self):
        """
        Обновляет путь к корневой папке, если она была перемещена.
        """
        root_folder = self.find_object_by_id(self.root_folder_id)

        if not root_folder:
            # Если корневая папка удалена, создаём новую
            return self.set_root_folder()

        self.root_folder_path = root_folder['path']
        return root_folder

    def create_root_folder(self, folder_name):
        """
        Создает корневую папку в облаке.
        """
        try:
            folder_info = self.create_folder(folder_name)
            if folder_info:
                _logger.info("Root folder created: %s", folder_info)
                return folder_info
            else:
                _logger.error("Failed to verify creation of root folder: %s", folder_name)
                return None
        except Exception as e:
            _logger.error("Error while creating root folder '%s': %s", folder_name, e)
            return None

# -*- End of file nextcloud/tools/nextcloud_api.py -*-