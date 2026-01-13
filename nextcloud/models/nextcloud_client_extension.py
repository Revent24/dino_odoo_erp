from odoo import models, _

class NextcloudClient(models.Model):
    _inherit = 'nextcloud.client'

    def action_test_connection(self):
        self.ensure_one()
        try:
            client = self._get_client()
            client.list('/')  # Простой тест соединения
            self.state = 'confirmed'
            return [
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Connection to Nextcloud successful'),
                        'type': 'success'
                    }
                },
                {
                    'type': 'ir.actions.act_window',
                    'name': 'Nextcloud Clients',
                    'res_model': 'nextcloud.client',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'current',
                    'view_id': self.env.ref('dino_erp.view_nextcloud_client_form').id,
                }
            ]
        except Exception as e:
            self.state = 'error'
            return [
                {
                    'type': 'ir.actions.act_window',
                    'name': 'Nextcloud Clients',
                    'res_model': 'nextcloud.client',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'current',
                    'view_id': self.env.ref('dino_erp.view_nextcloud_client_form').id,
                },
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Connection failed: %s') % str(e),
                        'type': 'danger'
                    }
                }
            ]

    def action_edit_connection(self):
        self.ensure_one()
        # Возвращаем в draft, чтобы разрешить редактирование
        self.state = 'draft'
        return [
            {
                'type': 'ir.actions.act_window',
                'name': 'Nextcloud Clients',
                'res_model': 'nextcloud.client',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
            },
            {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Edit mode'),
                'message': _('Connection unlocked for editing.'),
                'type': 'info',
                'sticky': False,
                }
            }
        ]
