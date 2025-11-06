# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ArbitrationCase(models.Model):
    _name = "qlk.arbitration.case"
    _description = "Arbitration Case"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Case Reference", required=True, tracking=True)
    case_number = fields.Char(string="Case Number", tracking=True)
    arbitration_center = fields.Char(string="Arbitration Center", tracking=True)
    claimant_id = fields.Many2one("res.partner", string="Claimant", tracking=True)
    respondent_id = fields.Many2one("res.partner", string="Respondent", tracking=True)
    responsible_employee_id = fields.Many2one("hr.employee", string="Responsible Lawyer", tracking=True)
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Responsible User",
        related="responsible_employee_id.user_id",
        store=True,
    )
    arbitrator_ids = fields.Many2many(
        "qlk.arbitration.arbitrator",
        string="Arbitrators",
    )
    start_date = fields.Date(string="Start Date", tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("waiting_award", "Awaiting Award"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    session_ids = fields.One2many("qlk.arbitration.session", "case_id", string="Sessions")
    memo_ids = fields.One2many("qlk.arbitration.memo", "case_id", string="Memos")
    award_ids = fields.One2many("qlk.arbitration.award", "case_id", string="Awards")
    notes = fields.Html(string="Notes")
    color = fields.Integer(string="Color")

    _sql_constraints = [
        ("arbitration_case_unique", "unique(case_number)", "Case number must be unique."),
    ]

    def name_get(self):
        result = []
        for record in self:
            label = record.name
            if record.case_number:
                label = f"{record.case_number} - {label}"
            result.append((record.id, label))
        return result

    @api.model
    def action_open_sessions(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Sessions",
            "res_model": "qlk.arbitration.session",
            "view_mode": "list,form",
            "domain": [("case_id", "=", self.env.context.get("active_id"))],
        }
