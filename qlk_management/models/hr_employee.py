# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HREmployee(models.Model):
    _inherit = "hr.employee"

    lawyer_hour_cost = fields.Float(string="Lawyer Hour Cost")
    employee_code = fields.Char(
        string="Employee Code",
        readonly=True,
        copy=False,
        index=True,
    )
    employee_document_ids = fields.One2many(
        "qlk.employee.document",
        "employee_id",
        string="Contracts & NDA",
    )
    employee_document_count = fields.Integer(
        compute="_compute_employee_document_count"
    )

    _sql_constraints = [
        ("employee_code_unique", "unique(employee_code)", "Employee Code must be unique."),
    ]

    @api.depends("employee_document_ids")
    def _compute_employee_document_count(self):
        for employee in self:
            employee.employee_document_count = len(employee.employee_document_ids)

    def _get_employee_code_sequence(self, year):
        seq_code = "hr.employee.code.%s" % year
        seq = self.env["ir.sequence"].sudo().search([("code", "=", seq_code)], limit=1)
        if not seq:
            self.env["ir.sequence"].sudo().create(
                {
                    "name": "Employee Code %s" % year,
                    "code": seq_code,
                    "prefix": "EMP",
                    "suffix": "/%s" % year,
                    "padding": 3,
                    "company_id": False,
                }
            )
        return seq_code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("employee_code"):
                continue
            create_date = vals.get("create_date")
            if create_date:
                year = fields.Datetime.to_datetime(create_date).year
            else:
                year = fields.Date.context_today(self).year
            seq_code = self._get_employee_code_sequence(year)
            vals["employee_code"] = self.env["ir.sequence"].sudo().next_by_code(seq_code)
        return super().create(vals_list)

    def action_open_employee_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Employee Documents",
            "res_model": "qlk.employee.document",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }
