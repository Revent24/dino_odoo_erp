#!/bin/bash
set -e

echo "Dumping DB..."
sudo -u postgres pg_dump -Fc -f /tmp/dino24_dev.dump dino24_dev
echo "Dump saved: /tmp/dino24_dev.dump"
echo

echo "Actions with 'tree' in view_mode:"
sudo -u postgres psql -d dino24_dev -c "SELECT a.id, a.name, a.view_mode, COALESCE(md.module||'.'||md.name,'(no xmlid)') AS xmlid FROM ir_act_window a LEFT JOIN ir_model_data md ON (md.model='ir.actions.act_window' AND md.res_id = a.id) WHERE a.view_mode LIKE '%tree%';"
echo

echo "Actions for module dino_erp_vendors:"
sudo -u postgres psql -d dino24_dev -c "SELECT md.res_id AS action_id, a.name, a.view_mode, md.module, md.name FROM ir_model_data md JOIN ir_act_window a ON a.id = md.res_id WHERE md.model='ir.actions.act_window' AND md.module='dino_erp_vendors';"
echo

echo "Updating actions of module dino_erp_vendors (replace tree->list)"
sudo -u postgres psql -d dino24_dev -c "UPDATE ir_act_window SET view_mode = replace(view_mode,'tree','list') WHERE id IN (SELECT res_id FROM ir_model_data WHERE model='ir.actions.act_window' AND module='dino_erp_vendors');"
sudo -u postgres psql -d dino24_dev -c "SELECT md.res_id AS action_id, a.name, a.view_mode FROM ir_model_data md JOIN ir_act_window a ON a.id = md.res_id WHERE md.model='ir.actions.act_window' AND md.module='dino_erp_vendors';"
echo "Done." 
