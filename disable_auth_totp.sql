UPDATE ir_module_module SET state='uninstalled' WHERE name IN ('auth_totp', 'auth_passkey', 'html_editor');
SELECT name, state FROM ir_module_module WHERE name IN ('auth_totp', 'auth_passkey', 'html_editor');
