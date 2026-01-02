{
    'name': 'Dino ERP: Динамическое управление производством',
    'version': '1.0',
    'summary': 'Минимальный модуль с одной моделью и меню',
    'description': 'Минимальный Odoo модуль: одна модель `dino.minimal`, одно поле `name` и пункт меню.',
    'author': 'Revent24',
    'category': 'Tools',
    'depends': ['base', 'mail', 'web', 'uom'] ,  # added uom for document lines and quick-create
    'data': [
        'finance/views/dino_bank_views.xml',
        'finance/views/bank_views.xml',
        'finance/views/dino_bank_transaction_views.xml',
        'finance/views/dino_currency_rate_views.xml',
        'finance/views/dino_cashbook_views.xml',
        'core/views/minimal_views.xml',

        # Documents module views (moved before projects to ensure views validate)
        # Wizard for importing specifications must be loaded before the document form that references it
        'documents/wizard/import_specification_excel_views.xml',
        'documents/views/dino_operation_document_views.xml',
        'documents/views/dino_operation_document_specification_views.xml',
        'documents/views/dino_nomenclature_quick_create.xml',

        'projects/views/dino_project_views_sale.xml',
        'projects/views/dino_project_views.xml',

        # Core security and shared data
        'core/security/ir.model.access.csv',
        'core/data/ir_sequence_data.xml',

        # Stock section views
        'stock/views/dino_component_views.xml',
        'stock/views/dino_stock_config_views.xml',
        'stock/views/dino_nomenclature_views.xml',
        'stock/views/dino_nomenclature_quick_create.xml',
        'stock/views/dino_component_category_views.xml',
        'stock/data/dino_uom_data.xml',
        'stock/security/ir.model.access.csv',
        'finance/security/ir.model.access.csv',

        'partners/views/dino_partners_actions.xml',
        'partners/views/dino_partners_views.xml',
        'partners/views/dino_partner_nomenclature_views.xml',
        'partners/views/dino_partner_tag_views.xml',
        'partners/views/dino_tax_system_views.xml',



        'finance/data/ir_cron_data.xml',
        'api_integration/security/ir.model.access.csv',
        'api_integration/views/dino_api_menu.xml',
        'api_integration/views/dino_api_endpoint_views.xml',
        'core/views/menu.xml',
    ],

    'application': True,
    'installable': True,
    
    'images': ['core/menu_icons/crm.png'],
}
