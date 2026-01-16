#
#  -*- File: nextcloud/tools/dav_api.py -*-
# 

from urllib.parse import quote, unquote

class NextcloudDAV:
    def __init__(self, client):
        self.client = client

    def rename(self, old_path, new_name, is_dir=False):
        """Переименование файла или папки"""
        path_parts = old_path.rstrip('/').split('/')
        path_parts[-1] = quote(new_name)
        new_path = "/".join(path_parts)
        if is_dir:
            new_path += '/'
        
        if old_path != new_path:
            headers = {'Destination': new_path}
            return self.client._req('MOVE', old_path, headers=headers)
        return False

    # def move(self, old_path, target_folder_path, name):
    #    """Перемещение в другую папку"""
    #    new_path = f"{target_folder_path.rstrip('/')}/{quote(name)}"
    #    headers = {'Destination': new_path}
    #    return self.client._req('MOVE', old_path, headers=headers)

    def delete(self, path):
        """Удаление"""
        return self.client._req('DELETE', path)

    def create_dir(self, parent_path, name):
        """Создание папки"""
        new_path = f"{parent_path.rstrip('/')}/{quote(name)}/"
        return self.client._req('MKCOL', new_path)

    def upload_file(self, parent_path, name, content):
        """Загрузка файла через PUT"""
        # Убеждаемся, что путь не заканчивается слэшем, а имя начинается с него
        target_path = f"{parent_path.rstrip('/')}/{quote(name)}"
        headers = {'Content-Type': 'application/octet-stream'}
        return self.client._req('PUT', target_path, data=content, headers=headers)

# End of file nextcloud/tools/dav_api.py