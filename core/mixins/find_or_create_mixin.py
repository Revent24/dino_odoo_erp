#
#  -*- File: core/mixins/find_or_create_mixin.py -*-
#
# -*- coding: utf-8 -*-
from odoo import models, api


class FindOrCreateMixin(models.AbstractModel):
    _name = 'mixin.find.or.create'
    _description = 'Mixin for find or create functionality'

    @api.model
    def find_or_create(self, search_domain, create_vals, update_vals=None):
        """Generic find or create method

        Args:
            search_domain (list): Domain to search for existing record
            create_vals (dict): Values to create new record
            update_vals (dict, optional): Values to update existing record

        Returns:
            record: Found or created record
        """
        record = self.search(search_domain, limit=1)
        if record:
            if update_vals:
                record.write(update_vals)
            return record
        return self.create(create_vals)# End of file core/mixins/find_or_create_mixin.py
