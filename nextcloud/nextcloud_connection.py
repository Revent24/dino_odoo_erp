# -*- coding: utf-8 -*-
import requests
import logging
import xml.etree.ElementTree as ET
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class NextcloudConnection(models.Model):
    _name = 'nextcloud.connection'
    _description = 'Nextcloud Connection Settings'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name', default='Nextcloud Configuration', required=True)
    active = fields.Boolean(default=True)
    
    # Credentials
    url = fields.Char(string='Nextcloud URL', required=True, help="e.g. https://cloud.example.com")
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='App Password', required=True, help="Generate an App Password in Nextcloud Security Settings")
    
    # Root Folder Configuration
    root_folder_name = fields.Char(string='Root Folder Name', default='Odoo Docs', required=True)
    root_folder_id = fields.Char(string='Root Folder ID (oc:id)', readonly=True, tracking=True, help="Unique ID from Nextcloud database")
    
    def _get_webdav_base_url(self):
        """Returns the base WebDAV URL for the user."""
        self.ensure_one()
        base = self.url.rstrip('/')
        # Standard Nextcloud WebDAV endpoint
        return f"{base}/remote.php/dav/files/{self.username}"

    def _request(self, method, path, data=None, headers=None):
        """Wrapper for requests to handle auth and errors."""
        if headers is None:
            headers = {}
        
        # Construct full URL. Path should be relative to WebDAV root or full URL.
        if not path.startswith('http'):
            url = f"{self._get_webdav_base_url()}/{path.lstrip('/')}"
        else:
            url = path

        try:
            response = requests.request(
                method, 
                url, 
                auth=(self.username, self.password), 
                data=data, 
                headers=headers,
                timeout=30
            )
            return response
        except requests.exceptions.RequestException as e:
            raise UserError(_("Connection Error: %s") % str(e))

    def action_setup_root_folder(self):
        """
        Main method to initialize connection.
        1. Checks if Root Folder exists by Name.
        2. If not, creates it.
        3. Retrieves and stores the oc:fileid.
        """
        self.ensure_one()
        root_name = self.root_folder_name.strip('/')
        
        # 1. Check/Get Info (PROPFIND)
        # We ask for oc:fileid specifically
        propfind_body = """<?xml version="1.0" encoding="utf-8" ?>
            <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
              <d:prop>
                <oc:fileid />
                <d:resourcetype />
              </d:prop>
            </d:propfind>
        """
        headers = {'Depth': '0', 'Content-Type': 'application/xml'}
        
        res = self._request('PROPFIND', root_name, data=propfind_body, headers=headers)
        
        if res.status_code == 404:
            # 2. Create if missing (MKCOL)
            _logger.info(f"Root folder '{root_name}' not found. Creating...")
            mkcol_res = self._request('MKCOL', root_name)
            if mkcol_res.status_code not in (201, 200):
                raise UserError(_("Could not create root folder. Nextcloud returned: %s") % mkcol_res.status_code)
            
            # Request info again to get ID
            res = self._request('PROPFIND', root_name, data=propfind_body, headers=headers)

        if res.status_code == 207: # Multi-Status (Success for WebDAV)
            # 3. Parse XML to extract ID
            try:
                tree = ET.fromstring(res.content)
                # Namespaces are tricky in ElementTree, usually need full URI
                ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
                
                file_id_node = tree.find('.//oc:fileid', ns)
                if file_id_node is not None:
                    self.root_folder_id = file_id_node.text
                    return True
            except Exception as e:
                raise UserError(_("Failed to parse Nextcloud response: %s") % str(e))
        
        raise UserError(_("Could not retrieve Root Folder ID. Status: %s") % res.status_code)