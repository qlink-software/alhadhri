# -*- coding: utf-8 -*-
from odoo import fields, models


LITIGATION_STAGE_CODE_SELECTION = [
    ("F", "First Instance"),
    ("A", "Appeal"),
    ("CA", "Cassation"),
    ("E", "Enforcement"),
]


class LitigationLevel(models.Model):
    _name = "litigation.level"
    _description = "Litigation Level"
    _order = "sequence, id"

    name = fields.Char(string="Litigation Level", required=True, translate=True)
    code = fields.Selection(
        selection=LITIGATION_STAGE_CODE_SELECTION,
        string="Stage Code",
        required=True,
        default="F",
        help="Code appended to the litigation sequence when a case is created for this level.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    def init(self):
        super().init()
        self.env.cr.execute("SELECT to_regclass('litigation_level')")
        if not self.env.cr.fetchone()[0]:
            return
        level_codes = {
            "qlk_management.litigation_level_first_instance": "F",
            "qlk_management.litigation_level_appeal": "A",
            "qlk_management.litigation_level_cassation": "CA",
            "qlk_management.litigation_level_enforcement": "E",
        }
        for xml_id, code in level_codes.items():
            level = self.env.ref(xml_id, raise_if_not_found=False)
            if level:
                level.code = code
        self.search([("code", "=", False)]).write({"code": "F"})
