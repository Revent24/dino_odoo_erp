# -*- File: nextcloud/tools/nextcloud_api.py -*-
import logging
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote
import os

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
    def get_path_by_id(client, file_id):
        """Возвращает чистый путь по fileid"""
        search_url = "/remote.php/dav/"
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
        <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
          <d:basicsearch>
            <d:select><d:prop><d:displayname/><oc:fileid/></d:prop></d:select>
            <d:from><d:scope><d:href>/files/{client.username}</d:href><d:depth>infinity</d:depth></d:scope></d:from>
            <d:where><d:eq><d:prop><oc:fileid/></d:prop><d:literal>{file_id}</d:literal></d:eq></d:where>
          </d:basicsearch>
        </d:searchrequest>"""
        
        res = client._req('SEARCH', search_url, data=body.encode('utf-8'), headers={'Content-Type': 'text/xml'})
        if res.status_code in [200, 207]:
            full_href = NextcloudConnector._parse_xml_response(res.content, 'href')
            if full_href:
                if "://" in full_href:
                    from urllib.parse import urlparse
                    return urlparse(full_href).path
                return full_href
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
    def rename_node(client, old_path, new_name, is_dir=False):
        """Универсальный MOVE"""
        clean_old_path = unquote(old_path).rstrip('/')
        base_dir = os.path.dirname(clean_old_path)
        
        if not is_dir:
            orig_name = os.path.basename(clean_old_path)
            if '.' in orig_name:
                ext = orig_name.rpartition('.')[-1]
                if new_name.lower().endswith(f".{ext.lower()}"):
                    new_name = new_name[:-(len(ext)+1)]
                new_name = f"{new_name}.{ext}"
        
        new_path = f"{base_dir}/{quote(new_name.strip())}"
        if is_dir: new_path += '/'

        dest_url = f"{client.url.rstrip('/')}{new_path}"
        res = client._req('MOVE', old_path, headers={'Destination': dest_url, 'Overwrite': 'F'})
        
        if res.status_code in [201, 204]:
            new_id, _ = NextcloudConnector.get_info_by_path(client, new_path)
            return new_path, new_id
        return False, False

    @staticmethod
    def ensure_path(client, parts):
        """Рекурсивное создание папок"""
        current_path = ""
        last_id = False
        for part in parts:
            if not part: continue
            part = part.strip('/')
            current_path += f"/{quote(part)}"
            res = client._req('PROPFIND', current_path + '/', headers={'Depth': '0'})
            if res.status_code == 404:
                client._req('MKCOL', current_path + '/')
                last_id, _ = NextcloudConnector.get_info_by_path(client, current_path + '/')
            else:
                last_id = NextcloudConnector._parse_xml_response(res.content, 'fileid')
        return current_path + '/', last_id
    
    @staticmethod
    def delete_node(client, path):
        """Удаляет файл или папку"""
        res = client._req('DELETE', path)
        return res.status_code in [200, 204]

# -*- End of file nextcloud/tools/nextcloud_api.py -*-