# -*- coding: utf-8 -*-

from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _visible_menu_ids(self, debug=False):
        return super()._visible_menu_ids(debug=debug)
