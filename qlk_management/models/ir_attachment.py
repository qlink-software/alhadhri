# -*- coding: utf-8 -*-
from odoo import fields, models


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    needs_translation = fields.Boolean(string="Needs Translation", default=False)
