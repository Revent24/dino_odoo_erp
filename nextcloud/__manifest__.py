{
    'name': 'Nextcloud Integration',
    'version': '1.0',
    'summary': 'Integration module for Nextcloud file storage with Odoo',
    'description': 'This module allows Odoo to interact with Nextcloud for file storage and synchronization.',
    'author': 'Your Name',
    'website': 'https://www.example.com',
    'category': 'Tools',
    'depends': ['base'],
    'external_dependencies': {},
    'data': [
        'security/ir.model.access.csv',
        'data/nextcloud_client_data.xml',
        'views/nextcloud_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}