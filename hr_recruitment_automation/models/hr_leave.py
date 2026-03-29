from dateutil.relativedelta import relativedelta

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class HrLeave(models.Model):
    _inherit = "hr.leave"

    # هذا الحقل يتيح للمدير تجاوز قيود السياسة في الحالات الاستثنائية.
    manager_override = fields.Boolean(string="Manager Override", tracking=True)

    def _get_employee_start_date(self, employee):
        self.ensure_one()
        first_contract = self.env["hr.contract"].search(
            [("employee_id", "=", employee.id)],
            order="date_start asc",
            limit=1,
        )
        if first_contract and first_contract.date_start:
            return first_contract.date_start
        return employee.create_date.date() if employee.create_date else fields.Date.context_today(self)

    def _check_custom_leave_policies(self):
        for leave in self:
            leave_type = leave.holiday_status_id.sudo()
            code = (leave_type.automation_code or "").strip().lower()

            # السماح بتجاوز السياسات فقط لمدير الإجازات.
            if leave.manager_override and not self.env.user.has_group("hr_holidays.group_hr_holidays_manager"):
                raise ValidationError(_("Only Time Off Managers can use Manager Override."))

            # سياسة الإجازة السنوية: لا يسمح قبل 6 أشهر إلا مع override.
            if code == "annual" and not leave.manager_override:
                employee_start = leave._get_employee_start_date(leave.employee_id)
                eligible_from = employee_start + relativedelta(months=6)
                request_start = leave.request_date_from or fields.Date.context_today(leave)
                if request_start < eligible_from:
                    raise ValidationError(
                        _(
                            "Annual leave is available only after 6 months of service. Eligible from: %(date)s",
                            date=eligible_from,
                        )
                    )

            # سياسة إجازة الحج: مرة واحدة فقط لكل موظف (إلا مع override).
            if code == "hajj" and not leave.manager_override:
                previous_hajj_count = self.search_count([
                    ("id", "!=", leave.id),
                    ("employee_id", "=", leave.employee_id.id),
                    ("holiday_status_id.automation_code", "=", "hajj"),
                    ("state", "=", "validate"),
                ])
                if previous_hajj_count:
                    raise ValidationError(_("Hajj leave can only be taken once per employee."))

    def action_approve(self):
        res = super().action_approve()
        # يتم فحص السياسة بعد الانتقال للحالة النهائية، وأي خطأ سيؤدي إلى rollback كامل.
        self.filtered(lambda leave: leave.state == "validate")._check_custom_leave_policies()
        return res

    def action_validate(self):
        res = super().action_validate()
        # فحص إضافي لمسارات الاعتماد الثنائية.
        self.filtered(lambda leave: leave.state == "validate")._check_custom_leave_policies()
        return res
