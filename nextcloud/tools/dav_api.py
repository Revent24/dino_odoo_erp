#
#  -*- File: nextcloud/tools/dav_api.py -*-
# 

from urllib.parse import quote, unquote
from ..models.nextcloud_api import NextcloudConnector

class NextcloudDAV:
    def __init__(self, client):
        self.client = client

    def rename(self, old_path, new_name, is_dir=False):
        """DEPRECATED: Use NextcloudConnector.rename_node instead"""
        return NextcloudConnector.rename_node(self.client, old_path, new_name, is_dir)

    # def move(self, old_path, target_folder_path, name):
    #    """Перемещение в другую папку"""
    #    new_path = f"{target_folder_path.rstrip('/')}/{quote(name)}"
    #    headers = {'Destination': new_path}
    #    return self.client._req('MOVE', old_path, headers=headers)

    def delete(self, path):
        """DEPRECATED: Use NextcloudConnector.delete_node instead"""
        return NextcloudConnector.delete_node(self.client, path)

    def create_dir(self, parent_path, name):
        """DEPRECATED: Use NextcloudConnector.ensure_path instead"""
        parts = parent_path.rstrip('/').split('/') + [name]
        path, _ = NextcloudConnector.ensure_path(self.client, parts)
        return path

    def upload_file(self, parent_path, name, content):
        """DEPRECATED: Implement upload in NextcloudConnector if needed"""
        # Убеждаемся, что путь не заканчивается слэшем, а имя начинается с него
        target_path = f"{parent_path.rstrip('/')}/{quote(name)}"
        headers = {'Content-Type': 'application/octet-stream'}
        return self.client._req('PUT', target_path, data=content, headers=headers)

# End of file nextcloud/tools/dav_api.py