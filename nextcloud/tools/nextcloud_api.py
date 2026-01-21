# -*- File: nextcloud/tools/nextcloud_api.py -*-
import logging
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote
import os
import time
import re
import json

_logger = logging.getLogger(__name__)

class NextcloudConnector:

    @staticmethod
    def _parse_xml_response(content, tag_name):
        """Универсальный парсер для WebDAV XML"""
        try:
            root = ET.fromstring(content)
            for elem in root.iter():
                if elem.tag.split('}')[-1] == tag_name:
                    return elem.text
            return False
        except Exception as e:
            _logger.error("Nextcloud XML Parse Error: %s", e)
            return False

    @staticmethod
    def _extract_fileid(response):
        """
        Извлекает ID и гарантированно удаляет ведущие нули (00000651 -> 651).
        """
        file_id = response.headers.get('OC-FileId')
        
        if not file_id:
            found = re.search(r'<(?:[^>]+:)?(?:fileid|id)>([^<]+)', response.text)
            if found:
                file_id = found.group(1)
        
        if file_id:
            # Сначала выцепляем только цифры
            digit_match = re.search(r'(\d+)', str(file_id))
            if digit_match:
                # Превращаем в int (убирает нули) и обратно в str
                clean_id = str(int(digit_match.group(1)))
                _logger.info("NC_DEBUG: ID очищен от нулей: %s -> %s", file_id, clean_id)
                return clean_id
                
        return file_id

    @staticmethod
    def get_path_by_id(client, file_id):
        """Возвращает чистый путь по fileid через SEARCH"""
        if not file_id:
            return False

        # Уточняем путь до эндпоинта файлов пользователя
        search_url = f"/remote.php/dav/files/{client.username}/"
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
        <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
          <d:basicsearch>
            <d:select>
                <d:prop><d:displayname/><oc:fileid/><d:getcontenttype/></d:prop>
            </d:select>
            <d:from>
                <d:scope>
                    <d:href>{search_url}</d:href>
                    <d:depth>infinity</d:depth>
                </d:scope>
            </d:from>
            <d:where>
                <d:eq>
                    <d:prop><oc:fileid/></d:prop>
                    <d:literal>{file_id}</d:literal>
                </d:eq>
            </d:where>
          </d:basicsearch>
        </d:searchrequest>"""

        try:
            res = client._req('SEARCH', search_url, data=body.encode('utf-8'), headers={'Content-Type': 'text/xml'})
            if res.status_code in [200, 207]:
                full_href = NextcloudConnector._parse_xml_response(res.content, 'href')
                if full_href:
                    # Убираем домен, если он есть в href
                    path = full_href.split('/remote.php/dav/')[1] if '/remote.php/dav/' in full_href else full_href
                    return "/remote.php/dav/" + unquote(path).lstrip('/')
        except Exception as e:
            _logger.error("NC_DEBUG: Search by ID %s failed: %s", file_id, e)

        return False

    @staticmethod
    def get_info_by_path(client, path):
        """Возвращает (fileid, current_path)"""
        res = client._req('PROPFIND', path, headers={'Depth': '0'})
        if res.status_code in [200, 207]:
            fileid = NextcloudConnector._parse_xml_response(res.content, 'fileid')
            return fileid, path
        return False, False

    @staticmethod
    def rename_node(client, old_path, new_full_path_raw):
        """Универсальное перемещение/переименование"""
        fs_prefix = f"/remote.php/dav/files/{client.username}"
        
        # Очищаем входящий путь от возможных префиксов, чтобы не было дублей
        clean_target = new_full_path_raw.replace(fs_prefix, '').strip('/')
        encoded_dest_path = f"{fs_prefix}/{quote(clean_target, safe='/')}"
        
        if not encoded_dest_path.endswith('/'):
            encoded_dest_path += '/'
            
        dest_url = f"{client.url.rstrip('/')}{encoded_dest_path}"
        
        _logger.info("NC_DEBUG: MOVE FROM: %s TO: %s", old_path, dest_url)
        
        res = client._req('MOVE', old_path, headers={
            'Destination': dest_url,
            'Overwrite': 'F'
        })
        
        if res.status_code in [201, 204]:
            return unquote(encoded_dest_path), True
        return False, False

    @staticmethod
    def ensure_path_v2(client, path_parts, path_ids_json=False, base_path='/'):
        _logger.info("NC_DEBUG: ensure_path_v2 for %s", path_parts)
        
        # 1. Берем логин из настроек клиента
        user = client.username

        # 2. Базовый путь для WebDAV в Nextcloud
        dav_root = f"/remote.php/dav/files/{user}"

        # Убеждаемся, что текущий путь начинается правильно
        current_path = dav_root
        new_ids = []

        # XML Body для запроса ID (обязательно для Nextcloud)
        prop_body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
            '  <d:prop>'
            '    <oc:id/>'
            '    <oc:fileid/>'
            '  </d:prop>'
            '</d:propfind>'
        )
        
        for i, part in enumerate(path_parts):
            test_path = f"{current_path}/{part}"
            # Кодируем путь, но слеши должны остаться слешами для URL
            test_path_enc = quote(test_path).replace('%2F', '/')

            _logger.info("NC_DEBUG: Sending PROPFIND to: %s", test_path_enc)

            res = client._req('PROPFIND', test_path_enc, data=prop_body, headers={'Depth': '0', 'Content-Type': 'text/xml'})

            # Логи для проверки (теперь должны быть 207 Multi-Status)
            _logger.info("NC_DEBUG: HTTP Status: %s", res.status_code)

            f_id = NextcloudConnector._extract_fileid(res)

            if f_id:
                new_ids.append(f_id)
                current_path = test_path
            else:
                # Если папки нет (404), пробуем создать (MKCOL)
                if res.status_code == 404:
                    mk_res = client._req('MKCOL', test_path_enc)
                    _logger.info("NC_DEBUG: Создана папка %s, статус: %s, тело: %s", 
                                 test_path_enc, mk_res.status_code, mk_res.text)
                    # Повторный запрос ID после создания
                    res = client._req('PROPFIND', test_path_enc, data=prop_body, headers={'Depth': '0', 'Content-Type': 'text/xml'})
                    f_id = NextcloudConnector._extract_fileid(res)
                    if f_id:
                        new_ids.append(f_id)
                        current_path = test_path
                        continue
                    else:
                        _logger.error("NC_DEBUG: Не удалось получить ID после создания папки. Response: %s", res.text)

                _logger.error("NC_DEBUG: Still no ID for '%s'. Response: %s", test_path, res.text)
                return False, False

        return current_path, new_ids

    @staticmethod
    def delete_node(client, path):
        res = client._req('DELETE', path)
        return res.status_code in [200, 204]

    @staticmethod
    def get_info_by_id(client, file_id):
        """
        Рекурсивный поиск пути по FileID (медленный, но надежный).
        """
        if not file_id:
            return None

        _logger.info("NC_API: Запуск рекурсивного поиска для ID: %s", file_id)
        
        # Начинаем поиск с корня пользователя
        root_url = f"/remote.php/dav/files/{client.username}/"
        
        # Внутренняя функция для рекурсии
        def search_recursive(url):
            prop_body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
                '  <d:prop>'
                '    <oc:fileid/>'
                '    <d:resourcetype/>'
                '  </d:prop>'
                '</d:propfind>'
            )
            
            res = client._req('PROPFIND', url, data=prop_body, headers={'Depth': '1', 'Content-Type': 'text/xml'})
            if res.status_code not in [200, 207]:
                return None
                
            tree = ET.fromstring(res.content)
            namespaces = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
            
            folders_to_scan = []

            for response in tree.findall(".//d:response", namespaces):
                href = unquote(response.find("d:href", namespaces).text)
                
                # Пропускаем саму папку, которую сканируем
                if href.rstrip('/') == url.rstrip('/'):
                    continue
                
                # Проверяем ID
                f_id_el = response.find(".//oc:fileid", namespaces)
                f_id_val = f_id_el.text.lstrip('0') if f_id_el is not None and f_id_el.text else False
                if f_id_val and str(f_id_val) == str(file_id).lstrip('0'):
                    return href

                # Если это папка, запоминаем для глубокого сканирования
                rt = response.find(".//d:resourcetype", namespaces)
                if rt is not None and rt.find("d:collection", namespaces) is not None:
                    folders_to_scan.append(href)
            
            # Если в текущем уровне не нашли, идем вглубь
            for folder_url in folders_to_scan:
                found = search_recursive(folder_url)
                if found:
                    return found
            
            return None

        try:
            found_path = search_recursive(root_url)
            if found_path:
                _logger.info("NC_API: Рекурсия нашла путь: %s", found_path)
                return {'path': found_path, 'id': file_id}
            
            _logger.warning("NC_API: ID %s не найден после полного сканирования.", file_id)
            return None
        except Exception as e:
            _logger.error("NC_API: Ошибка рекурсии: %s", str(e))
            return None

# -*- End of file nextcloud/tools/nextcloud_api.py -*-