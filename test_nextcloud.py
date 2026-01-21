#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/home/steve/OdooApps/odoo19')

import odoo
from odoo import api, SUPERUSER_ID
from odoo.tools import config

# Parse config
config.parse_config([])

# Connect to database
db = 'dino24_dev'
cr = odoo.sql_db.db_connect(db).cursor()
registry = odoo.registry(db)
env = api.Environment(cr, SUPERUSER_ID, {})

# Check if nextcloud_client exists
try:
    clients = env['nextcloud.client'].search([])
    print(f"Nextcloud clients: {len(clients)}")
    for client in clients:
        print(f"Client: {client.name}, URL: {client.url}, State: {client.state}")
except Exception as e:
    print(f"Error accessing nextcloud.client: {e}")

# Check project categories
try:
    categories = env['dino.project.category'].search([])
    print(f"Project categories: {len(categories)}")
    for cat in categories:
        print(f"Category: {cat.name}, ID: {cat.id}")
except Exception as e:
    print(f"Error accessing project categories: {e}")

# Create a test project
try:
    # Get first category
    category = env['dino.project.category'].search([], limit=1)
    if category:
        project_data = {
            'name': 'Test Nextcloud Project',
            'project_category_id': category.id,
        }
        project = env['dino.project'].create(project_data)
        print(f"Created project: {project.name}, ID: {project.id}")
        
        # Try to ensure Nextcloud folder
        if hasattr(project, 'action_ensure_nc_folder'):
            try:
                project.action_ensure_nc_folder()
                print("Nextcloud folder ensured successfully")
            except Exception as e:
                print(f"Error ensuring Nextcloud folder: {e}")
        else:
            print("Project does not have action_ensure_nc_folder method")
    else:
        print("No project categories found")
except Exception as e:
    print(f"Error creating project: {e}")

cr.close()