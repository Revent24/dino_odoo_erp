odoo.define('dino_erp.category_sidebar', function(require) {
    'use strict';
    var rpc = require('web.rpc');
    var Widget = require('web.Widget');
    var ListController = require('web.ListController');

    function buildTree(items) {
        var lookup = {};
        items.forEach(function(it){ lookup[it.id] = $.extend({}, it, {children: [], count: it.count || 0}); });
        var root = [];
        items.forEach(function(it){
            var pid = false;
            if (it.parent_id) {
                pid = Array.isArray(it.parent_id) ? it.parent_id[0] : (it.parent_id && it.parent_id[0]) || false;
            }
            if (pid) {
                var p = lookup[pid];
                if (p) p.children.push(lookup[it.id]);
                else root.push(lookup[it.id]);
            } else {
                root.push(lookup[it.id]);
            }
        });
        function render(nodes){
            var $ul = $('<ul class="o_dino_cat_tree"/>');
            nodes.forEach(function(n){
                var $li = $('<li/>');
                var $a = $('<a href="#" class="dino-cat" data-id="'+n.id+'">').text(n.name + (n.count ? ' ('+n.count+')' : ''));
                $li.append($a);
                if (n.children && n.children.length) {
                    $li.append(render(n.children));
                }
                $ul.append($li);
            });
            return $ul;
        }
        return render(root);
    }

    var CategorySidebar = Widget.extend({
        template: false,
        events: { 'click .dino-cat': '_onClickCat' },
        start: async function() {
            var categories = await rpc.query({
                model: 'dino.component.category',
                method: 'get_tree_with_counts',
                args: [],
            });
            this.$el.empty().append('<div class="dino-cat-header"><h4>Категории</h4><button class="btn btn-sm btn-light dino-reset">Сброс</button></div>');
            this.$el.append(buildTree(categories));
            this.$el.on('click', '.dino-reset', this._onReset.bind(this));
        },
        _onReset: function(ev) {
            ev && ev.preventDefault();
            this.trigger_up('dino_category_selected', {id: false});
            this.$el.find('.dino-cat.selected').removeClass('selected');
        }
        _onClickCat: function(ev) {
            ev.preventDefault();
            var $t = $(ev.currentTarget);
            var id = parseInt($t.data('id'), 10);
            this.$el.find('.dino-cat.selected').removeClass('selected');
            $t.addClass('selected');
            this.trigger_up('dino_category_selected', {id: id});
        }
    });

    ListController.include({
        start: function() {
            var res = this._super.apply(this, arguments);
            if (this.modelName === 'dino.nomenclature') {
                var $row = this.$el.closest('.o_view_manager_row');
                var $cp_left = $row.find('.o_cp_left');
                if ($cp_left.length === 0) {
                    var $cp = $row.find('.o_cp');
                    if (!$cp.length) {
                        $cp = $row.find('.o_control_panel');
                    }
                    if ($cp.length) {
                        $cp_left = $('<div class="o_cp_left"/>').prependTo($cp);
                    } else {
                        // fallback: attach to view element
                        $cp_left = $('<div class="o_cp_left"/>').prependTo(this.$el);
                    }
                }
                this._categorySidebar = new CategorySidebar(this);
                this._categorySidebar.appendTo($cp_left);
                this._categorySidebar.on('dino_category_selected', this, this._onCategorySelected);
            }
            return res;
        },
        _onCategorySelected: function(ev) {
            var id = ev.id || (ev.data && ev.data.id);
            if (!id) { this.reload({domain: []}); return; }
            this.reload({domain: [['category_id', 'child_of', id]]});
        }
    });

    return CategorySidebar;
});