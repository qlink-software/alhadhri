# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models


class HREmployee(models.Model):
    _inherit = "hr.employee"

    lawyer_hour_cost = fields.Float(string="Lawyer Hour Cost")
    is_mp = fields.Boolean(
        string="MP",
        tracking=True,
        help="Marks employees who should receive Managing Partner request notifications.",
    )
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
    employee_document_count = fields.Integer(compute="_compute_employee_document_count")
    resignation_request_ids = fields.One2many(
        "hr.resignation.request",
        "employee_id",
        string="Resignation Requests",
    )
    resignation_request_count = fields.Integer(
        string="Resignation Requests",
        compute="_compute_resignation_request_count",
    )

    # هذا الحقل لتسجيل اعتماد الاستقالة وبدء فترة الإشعار القانونية.
    resignation_approved = fields.Boolean(string="Resignation Approved", tracking=True)
    # هذا الحقل يمثل تاريخ تقديم/اعتماد الاستقالة على ملف الموظف.
    resignation_date = fields.Date(string="Resignation Date", tracking=True)
    approval_date = fields.Date(string="Approval Date", tracking=True)
    effective_date = fields.Date(string="Effective Date", tracking=True)
    # حقل توافق مع المنطق السابق، ويرتبط الآن بتاريخ انتهاء الوصول الفعلي.
    notice_end_date = fields.Date(
        string="Notice End Date",
        related="effective_date",
        store=True,
        readonly=True,
    )
    # هذا الحقل يتتبع إن كان تم إيقاف حساب المستخدم بعد انتهاء الإشعار.
    user_deactivated_after_notice = fields.Boolean(
        string="User Deactivated After Notice",
        readonly=True,
        copy=False,
        default=False,
    )

    _sql_constraints = [
        ("employee_code_unique", "unique(employee_code)", "Employee Code must be unique."),
    ]

    @api.depends("employee_document_ids")
    def _compute_employee_document_count(self):
        for employee in self:
            employee.employee_document_count = len(employee.employee_document_ids)

    @api.depends("resignation_request_ids")
    def _compute_resignation_request_count(self):
        for employee in self:
            employee.resignation_request_count = len(employee.resignation_request_ids)

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
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if vals.get("resignation_approved") and not vals.get("approval_date"):
                vals["approval_date"] = today
            if vals.get("resignation_approved") and not vals.get("resignation_date"):
                vals["resignation_date"] = today
            if vals.get("resignation_approved") and not vals.get("effective_date"):
                base_date = fields.Date.to_date(vals.get("approval_date")) if vals.get("approval_date") else today
                vals["effective_date"] = base_date + timedelta(days=15)
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

    def write(self, vals):
        # هذه الخطوة تضمن تعيين تواريخ الاعتماد والانتهاء تلقائيًا عند الاعتماد لأول مرة.
        if vals.get("resignation_approved"):
            today = fields.Date.context_today(self)
            if not vals.get("approval_date"):
                vals["approval_date"] = today
            if not vals.get("resignation_date"):
                vals["resignation_date"] = today
            if not vals.get("effective_date"):
                base_date = fields.Date.to_date(vals.get("approval_date")) if vals.get("approval_date") else today
                vals["effective_date"] = base_date + timedelta(days=15)
        elif vals.get("resignation_approved") is False:
            vals.setdefault("approval_date", False)
            vals.setdefault("effective_date", False)
        return super().write(vals)

    # ------------------------------------------------------------------------------
    # هذا المنطق لإيقاف المستخدم بعد فترة الإشعار تلقائيًا.
    # ------------------------------------------------------------------------------
    @api.model
    def cron_deactivate_users_after_notice(self):
        today = fields.Date.context_today(self)
        expired = self.search(
            [
                ("resignation_approved", "=", True),
                ("effective_date", "!=", False),
                ("effective_date", "<=", today),
                ("user_id", "!=", False),
            ]
        )
        for employee in expired:
            if employee.user_id.active:
                employee.user_id.sudo().write({"active": False})
                employee.message_post(
                    body=_("User access revoked automatically after the approved resignation notice period ended.")
                )
            if not employee.user_deactivated_after_notice:
                employee.sudo().write({"user_deactivated_after_notice": True})
        return True

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

    def action_open_resignation_requests(self):
        self.ensure_one()
        action = self.env.ref(
            "qlk_management.action_hr_resignation_requests",
            raise_if_not_found=False,
        )
        if not action:
            return False
        action_vals = action.read()[0]
        action_vals["domain"] = [("employee_id", "=", self.id)]
        action_vals.setdefault("context", {})
        action_vals["context"].update({"default_employee_id": self.id})
        return action_vals
