# -*- coding: utf-8 -*-
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def load_menus(self, debug):
        if not self.env.context.get("qlk_skip_menu_sanitize"):
            self.env["qlk.project.removal.cleanup"].with_context(
                qlk_skip_menu_sanitize=True
            )._sanitize_broken_menu_actions()
        return super().load_menus(debug)
