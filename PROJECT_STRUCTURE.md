# Структура файлов проекта

## Корневая директория
```
__init__.py
__manifest__.py
ai_template_OLD.md
check_modules.sql
Dino_ERP.md
disable_auth_totp.sql
l -e psql -d dino24_dev -c SELECT id, name, url, username, state FROM nextcloud_client;
l -e psql -d dino24_dev -c SELECT id,module,name,model,res_id FROM ir_model_data WHERE name ILIKE '-nextcloud-';
l -e psql -d dino24_dev -c SELECT pt.id, pt.name, pt.project_category_id, pc.name as category_name FROM dino_project_type pt LEFT JOIN dino_project_category pc ON pt.project_category_id = pc.id;
LICENSE
odoo_info.md
OPTIMIZATION_REPORT.md
post_init_hook.py
pre_init_hook.py
README.md
run_server_commands.md
simple_test.py
test_nextcloud.py

```

## Каталог `api_integration`
```
data/
    ir_cron_data.xml
migrations/
models/
security/
services/
static/
views/
```

## Каталог `core`
```
main_menu_actions.xml
main_menu_actions.xml.bak
main_menu.xml
data/
menu_icons/
mixins/
security/
```

## Каталог `documents`
```
IMPORT_LOGIC.md
PARSER_AGENTS_GUIDE.md
data/
migrations/
models/
scripts/
security/
services/
tests/
views/
wizard/
```

## Каталог `finance`
```
data/
migrations/
models/
security/
services/
views/
wizard/
```

## Каталог `manufacturing`
```
(структура не указана)
```

## Каталог `nextcloud`
```
hooks.py
nextcloud.md
data/
    nextcloud_client_data.xml
mixins/
    nc_node_mixin.py
    nextcloud_base_mixin.py
    nextcloud_flat_mixin.py
    nextcloud_project_mixin.py
models/
    nextcloud_client.py
    nextcloud_file.py
    nextcloud_root_map.py
security/
    ir.model.access.csv
tools/
    dav_api.py
    nc_connector.py
    nc_xml_templates.py
    nextcloud_api.py
    nextcloud_xml_utils.py
views/
    nextcloud_client_views.xml
    nextcloud_file_views.xml
    nextcloud_root_map_views.xml
```

## Каталог `partners`
```
data/
models/
scripts/
views/
```

## Каталог `projects`
```
data/
    project_categories.xml
    project_types.xml
models/
    dino_project_category.py
    dino_project_payment.py
    dino_project_type.py
    dino_project.py
security/
    ir.model.access.csv
views/
    dino_project_type_views.xml
    dino_project_views_sale.xml
    dino_project_views.xml
    dino_project_views.xml.patch
```

## Каталог `purchase`
```
(структура не указана)
```

## Каталог `sales`
```
(структура не указана)
```

## Каталог `scripts`
```
add_partner_fields.py
run_balance_check.py
run_cron_fetch_rates.py
run_health_check.py
run_import_nbu.py
test_mixin.py
test_price_recalculation.py
test_privat_balances.py
```

## Каталог `stock`
```
data/
migrations/
models/
security/
static/
views/
```

## Каталог `tests`
```
test_api_endpoint.py
test_find_or_create_mixin.py
test_nbu_client.py
test_nbu_service.py
test_privat_client.py
test_privat_service.py
```