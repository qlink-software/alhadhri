# -*- coding: utf-8 -*-

from odoo import fields, models


class CorporateCase(models.Model):
    _name = "qlk.corporate.case"
    _description = "Corporate Case"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Company / Case Name", required=True, tracking=True)
    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        tracking=True,
        domain="[('customer', '=', True)]",
    )
    service_type = fields.Selection(
        selection=[
            ("incorporation", "Company Incorporation"),
            ("contract", "Commercial Contract"),
            ("trademark", "Trademark Registration"),
            ("advisory", "Ongoing Advisory"),
            ("other", "Other"),
        ],
        string="Service Type",
        default="incorporation",
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("waiting", "Waiting"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    responsible_employee_id = fields.Many2one(
        "hr.employee",
        string="Responsible Lawyer",
        tracking=True,
        required=True,
    )
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Responsible User",
        related="responsible_employee_id.user_id",
        store=True,
    )
    memo_ids = fields.One2many("qlk.corporate.memo", "case_id", string="Memos")
    contract_ids = fields.One2many("qlk.corporate.contract", "case_id", string="Contracts")
    consultation_ids = fields.One2many("qlk.corporate.consultation", "case_id", string="Consultations")
    document_ids = fields.One2many("qlk.corporate.document", "case_id", string="Documents")
    color = fields.Integer("Color")
    notes = fields.Html(string="Internal Notes")

    _sql_constraints = [
        ("corporate_case_name_unique", "unique(name)", "A corporate case with this name already exists."),
    ]

    def name_get(self):
        result = []
        for record in self:
            label = record.name
            if record.client_id:
                label = f"{label} - {record.client_id.name}"
            result.append((record.id, label))
        return result
