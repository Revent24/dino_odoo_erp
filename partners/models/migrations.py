#
#  -*- File: partners/models/migrations.py -*-
#
"""Migration utilities removed.

This file previously provided a wrapper to run tax-system cleanup/migration.
The Tax Systems feature has been removed; keep a harmless placeholder to avoid import errors.
"""

from odoo import models


class DinoPartnerMigrationPlaceholder(models.TransientModel):
    _name = 'dino.partner.migration'
    _description = 'Placeholder (tax systems removed)'

    def noop(self):
        return True
# End of file partners/models/migrations.py
