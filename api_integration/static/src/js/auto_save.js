odoo.define('dino_erp.auto_save', function (require) {
    "use strict";
    var FormController = require('web.FormController');

    FormController.include({
        _onFieldChanged: function (record, ev) {
            this._super.apply(this, arguments);
            // Автосохранение только когда active=False (форма редактируемая)
            console.log('Field changed, model:', this.modelName, 'active:', record.data.active, 'mode:', this.mode);
            if (this.mode === 'edit' && this.modelName === 'dino.api.endpoint' && !record.data.active) {
                console.log('Auto-saving...');
                this.saveRecord();
            }
        }
    });
});