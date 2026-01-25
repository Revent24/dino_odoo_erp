# -*- File: nextcloud/tools/nextcloud_api.py -*-
import logging
import requests
import os
from lxml import etree
from urllib.parse import unquote

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
        - Если указан file_id, выполняется поиск по ID.
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

    def find_in_folder(self, parent_id, child_name):
        """
        Ищет дочерний объект по имени внутри папки-родителя.
        Использует универсальную функцию _find_object.
        """
        return self._find_object(parent_id=parent_id, name=child_name)

    def ensure_path_step(self, parent_id, segment_name):
        """
        Обеспечивает наличие папки и возвращает её ID.
        """
        _logger.info("Ensuring segment '%s' in parent ID %s", segment_name, parent_id)
        child_info = self._find_object(parent_id=parent_id, name=segment_name)

        if not child_info:
            parent_info = self.get_object_data(file_id=parent_id)
            if not parent_info:
                raise ValueError(f"Parent folder {parent_id} not found on server.")

            # Создаем новую папку
            new_folder_path = f"{parent_info['path']}/{segment_name}"
            self._do_request('MKCOL', path=new_folder_path)
            child_info = self._find_object(parent_id=parent_id, name=segment_name)

        return child_info['file_id'] if child_info else None

    def find_by_id(self, file_id, path_scope=None):
        """
        Ищет объект по File-ID через универсальную функцию _find_object.
        """
        return self._find_object(file_id=file_id)

    def get_object_data(self, path=None, file_id=None):
        """
        Выполняет запрос PROPFIND с заголовком {'Depth': '0'}.
        Возвращает словарь с данными: file_id, href, name, is_folder, path.
        Если передан file_id, использует универсальную функцию _find_object.
        """
        if file_id and not path:
            return self._find_object(file_id=file_id)

        headers = {'Depth': '0', 'Content-Type': 'application/xml; charset=utf-8'}
        body = (
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
            '<d:prop><d:displayname/><d:resourcetype/><oc:fileid/></d:prop>'
            '</d:propfind>'
        )

        response = self._do_request('PROPFIND', path=path, headers=headers, data=body)
        if response.status_code not in (200, 207):
            return None

        try:
            root = etree.fromstring(response.content)
            ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
            resp = root.find('.//d:response', ns)
            if resp is None:
                return None
            return self._get_info_from_response(resp, ns)
        except Exception as e:
            _logger.error("Error parsing PROPFIND response: %s", e)
            return None

# -*- End of file nextcloud/tools/nextcloud_api.py -*-