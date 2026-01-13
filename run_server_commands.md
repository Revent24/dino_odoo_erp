## 💻 Команды для запуска сервера Odoo

Файл с командами, которые вы использовали при разработке первого модуля. Сохранён для повторного использования и инструкций.

```bash
# 1. Запустить Ubuntu/WSL (это вы делаете вручную)

cd ~/OdooApps/odoo19
source .venv/bin/activate
python3 odoo-bin -d dino24_dev -u dino_erp --addons-path=addons,../odoo_projects/dino24_addons --db_user=steve --http-port=8070

# 2. Активировать виртуальное окружение
source ~/OdooApps/odoo19-venv/bin/activate

# 3. Перейти в папку Odoo
cd ~/OdooApps/odoo19

# 4. Запустить сервер
python3 -m odoo server -d dino24_dev --addons-path=addons,../odoo_projects/dino24_addons --db_user=steve --http-port=8070

# Запустить сервер с принудительным обновлением модуля dino_erp
source ~/OdooApps/odoo_projects/dino24_addons/.venv/bin/activate
cd ~/OdooApps/odoo19
python3 -m odoo server -d dino24_dev -u dino_erp --addons-path=addons,../odoo_projects/dino24_addons --db_user=steve --http-port=8070

# или пересборка web.assets
python3 -m odoo server -d dino24_dev --addons-path=addons,../odoo_projects/dino24_addons --dev=assets


# Запустить сервер с принудительным обновлением модуля dino_erp_operations
python3 -m odoo server -d dino24_dev -u dino_erp_vendors --addons-path=addons,../odoo_projects/dino24_addons --db_user=steve --http-port=8070






# Запустить сервер с обновлением модуля
python3 -m odoo server -d dino24_dev -u dino_erp --addons-path=addons,../odoo_projects/dino24_addons --db_user=steve --http-port=8070




# Интерфейс
# Перейти на http://localhost:8070/odoo/discuss

# Операции с базой
## Открыть базу
sudo -u postgres psql -d dino24_dev

# Обновление языков интерфейса
# Экспорт русского языка (ru.po)
python3 -m odoo --addons-path=addons,../odoo_projects/dino24_addons i18n export -d dino24_dev -l ru_RU -o /home/steve/OdooApps/odoo_projects/dino24_addons/dino_erp_stock/i18n/ru.po dino_erp_stock

# Экспорт украинского языка (uk.po)
python3 -m odoo --addons-path=addons,../odoo_projects/dino24_addons i18n export -d dino24_dev -l uk_UA -o /home/steve/OdooApps/odoo_projects/dino24_addons/dino_erp_stock/i18n/uk.po dino_erp_stock

# Импорт переводов в базу данных (с перезаписью)
python3 -m odoo server -d dino24_dev -u dino_erp_stock --addons-path=addons,../odoo_projects/dino24_addons --db_user=steve --http-port=8070 --i18n-overwrite
```


Установка webdavclient3

cd /home/steve/OdooApps/odoo_projects/dino24_addons/dino_erp
source .venv/bin/activate  # или как называется твоя папка venv
pip install webdavclient3