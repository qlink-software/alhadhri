import logging
from datetime import date, datetime, time, timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # هذا الربط يحتفظ بسجل طلب التوظيف الذي تم منه إنشاء الموظف.
    applicant_origin_id = fields.Many2one("hr.applicant", string="Recruitment Applicant", copy=False, readonly=True)
    # هذا الحقل يطبق صيغة كود الموظف EMP/0001/YYYY المطلوبة.
    recruitment_employee_code = fields.Char(string="Recruitment Employee Code", copy=False, readonly=True, index=True)
    # هذا الحقل يحفظ نوع التوظيف القادم من مرحلة الـ Recruitment.
    employment_type = fields.Selection(
        [("full_time", "Full-time"), ("part_time", "Part-time")],
        string="Employment Type",
        default="full_time",
    )
    # هذا الحقل يحفظ تاريخ مباشرة الموظف داخل الشركة دون الاعتماد على العقد فقط.
    date_of_joining = fields.Date(string="Date of Joining")
    # هذا الحقل يسمح بحفظ التحويلة الداخلية لهاتف العمل.
    work_phone_extension = fields.Char(string="Work Phone Extension")
    # هذا الحقل يوفر حالة تشغيلية واضحة للموظف داخل واجهة الموارد البشرية.
    status = fields.Selection(
        [
            ("active", "Active"),
            ("on_leave", "On Leave"),
            ("resigned", "Resigned"),
        ],
        string="Status",
        default="active",
    )
    # هذا الحقل يربط الموظف بمعرفه داخل جهاز البصمة.
    biometric_user_code = fields.Char(string="Biometric User Code", index=True)

    # هذه الحقول لتنفيذ منطق الاستقالة وفترة الإشعار.
    resignation_approved = fields.Boolean(string="Resignation Approved", copy=False)
    resignation_date = fields.Date(string="Resignation Date", copy=False)
    notice_period_end = fields.Date(
        string="Notice Period End",
        compute="_compute_notice_period_end",
        store=True,
        copy=False,
    )

    daily_target_hours = fields.Float(string="Daily Target Hours", default=8.0)

    # هذه الحقول تعرض لوحة HR داخل شاشة الموظف.
    dashboard_daily_hours = fields.Float(string="Today Hours", compute="_compute_dashboard_metrics")
    dashboard_weekly_hours = fields.Float(string="Weekly Hours", compute="_compute_dashboard_metrics")
    dashboard_required_hours = fields.Float(string="Required Hours", compute="_compute_dashboard_metrics")
    dashboard_missing_hours = fields.Float(string="Missing Hours", compute="_compute_dashboard_metrics")
    dashboard_leave_total = fields.Float(string="Leave Total", compute="_compute_dashboard_metrics")
    dashboard_leave_used = fields.Float(string="Leave Used", compute="_compute_dashboard_metrics")
    dashboard_leave_remaining = fields.Float(string="Leave Remaining", compute="_compute_dashboard_metrics")
    dashboard_pending_requests_count = fields.Integer(string="Pending Requests", compute="_compute_dashboard_metrics")
    dashboard_alerts = fields.Html(string="Alerts", compute="_compute_dashboard_metrics")

    _sql_constraints = [
        (
            "recruitment_employee_code_unique",
            "unique(recruitment_employee_code)",
            "Employee code must be unique.",
        ),
    ]

    @api.depends("resignation_date", "resignation_approved")
    def _compute_notice_period_end(self):
        for employee in self:
            if employee.resignation_approved and employee.resignation_date:
                employee.notice_period_end = employee.resignation_date + timedelta(days=15)
            else:
                employee.notice_period_end = False

    def _get_week_bounds(self):
        today = fields.Date.context_today(self)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        return week_start, week_end, today

    def _get_expected_hours_until_today(self):
        week_start, week_end, today = self._get_week_bounds()
        expected = 0.0
        cursor = week_start
        while cursor <= today:
            if cursor.weekday() < 5:
                expected += self.daily_target_hours or 8.0
            cursor += timedelta(days=1)
        return expected

    def _get_attendance_hours_for_period(self, date_from, date_to):
        self.ensure_one()
        start_dt = datetime.combine(date_from, time.min)
        end_dt = datetime.combine(date_to + timedelta(days=1), time.min)
        attendances = self.env["hr.attendance"].search([
            ("employee_id", "=", self.id),
            ("check_in", ">=", fields.Datetime.to_string(start_dt)),
            ("check_in", "<", fields.Datetime.to_string(end_dt)),
        ])
        return sum(attendances.mapped("worked_hours"))

    def _get_leave_balance_snapshot(self):
        self.ensure_one()
        allocations = self.env["hr.leave.allocation"].search([
            ("employee_id", "=", self.id),
            ("state", "=", "validate"),
        ])
        total_allocated = sum(allocations.mapped("number_of_days"))

        approved_leaves = self.env["hr.leave"].search([
            ("employee_id", "=", self.id),
            ("state", "=", "validate"),
        ])
        used_days = sum(approved_leaves.mapped("number_of_days"))

        pending_count = self.env["hr.leave"].search_count([
            ("employee_id", "=", self.id),
            ("state", "in", ["confirm", "validate1"]),
        ])

        remaining = max(total_allocated - used_days, 0.0)
        return total_allocated, used_days, remaining, pending_count

    @api.depends("attendance_ids.check_in", "attendance_ids.check_out", "attendance_ids.worked_hours")
    def _compute_dashboard_metrics(self):
        for employee in self:
            today = fields.Date.context_today(employee)
            week_start, week_end, current_day = employee._get_week_bounds()

            daily_hours = employee._get_attendance_hours_for_period(today, today)
            weekly_hours = employee._get_attendance_hours_for_period(week_start, today)
            required_hours = employee._get_expected_hours_until_today()
            missing_hours = max(required_hours - weekly_hours, 0.0)
            total_leave, used_leave, remaining_leave, pending_count = employee._get_leave_balance_snapshot()

            alerts = []
            if missing_hours > 0:
                alerts.append(_("Weekly working hours are below the expected threshold."))
            if pending_count:
                alerts.append(_("You have pending leave requests awaiting approval."))
            if employee.notice_period_end and employee.notice_period_end <= today:
                alerts.append(_("Notice period has ended. Deactivation is pending cron execution."))

            employee.dashboard_daily_hours = daily_hours
            employee.dashboard_weekly_hours = weekly_hours
            employee.dashboard_required_hours = required_hours
            employee.dashboard_missing_hours = missing_hours
            employee.dashboard_leave_total = total_leave
            employee.dashboard_leave_used = used_leave
            employee.dashboard_leave_remaining = remaining_leave
            employee.dashboard_pending_requests_count = pending_count
            employee.dashboard_alerts = "<br/>".join(alerts) if alerts else _("No alerts")

    def action_approve_resignation(self):
        for employee in self:
            employee.write(
                {
                    "resignation_approved": True,
                    "resignation_date": employee.resignation_date or fields.Date.context_today(employee),
                }
            )

    def action_open_employee_pending_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pending Time Off Requests"),
            "res_model": "hr.leave",
            "view_mode": "list,form,calendar",
            "domain": [
                ("employee_id", "=", self.id),
                ("state", "in", ["confirm", "validate1"]),
            ],
            "context": {"default_employee_id": self.id},
        }

    def action_open_employee_week_attendance(self):
        self.ensure_one()
        week_start, week_end, current_day = self._get_week_bounds()
        start_dt = datetime.combine(week_start, time.min)
        end_dt = datetime.combine(week_end + timedelta(days=1), time.min)
        return {
            "type": "ir.actions.act_window",
            "name": _("Weekly Attendance"),
            "res_model": "hr.attendance",
            "view_mode": "list,form,graph,pivot",
            "domain": [
                ("employee_id", "=", self.id),
                ("check_in", ">=", fields.Datetime.to_string(start_dt)),
                ("check_in", "<", fields.Datetime.to_string(end_dt)),
            ],
            "context": {"default_employee_id": self.id},
        }

    @api.model
    def _generate_recruitment_employee_code(self):
        # هذا التسلسل يُستخدم حصريًا لصيغة EMP/0001/YYYY.
        sequence_number = self.env["ir.sequence"].next_by_code("hr.recruitment.employee.code") or "0001"
        year = fields.Date.context_today(self).year
        return f"EMP/{sequence_number}/{year}"

    @api.model
    def cron_deactivate_after_notice_period(self):
        # هذا الكرون يُعطل المستخدم والموظف بعد انتهاء فترة الإشعار 15 يوم.
        today = fields.Date.context_today(self)
        employees = self.search([
            ("resignation_approved", "=", True),
            ("notice_period_end", "!=", False),
            ("notice_period_end", "<=", today),
            ("active", "=", True),
        ])
        for employee in employees:
            employee.active = False
            if employee.user_id:
                employee.user_id.sudo().active = False

    @api.model
    def cron_send_weekly_hours_reminder(self):
        # هذا الكرون يرسل تنبيه أسبوعي يوم الأربعاء للـ Managing Partner.
        today = fields.Date.context_today(self)
        if today.weekday() != 2:  # Wednesday
            return

        employees = self.search([("active", "=", True), ("company_id", "=", self.env.company.id)])
        missing_lines = []
        for employee in employees:
            expected = employee._get_expected_hours_until_today()
            week_start, week_end, current_day = employee._get_week_bounds()
            weekly_hours = employee._get_attendance_hours_for_period(week_start, today)
            if weekly_hours + 0.01 < expected:
                missing_lines.append(
                    {
                        "employee": employee,
                        "expected": round(expected, 2),
                        "actual": round(weekly_hours, 2),
                        "missing": round(expected - weekly_hours, 2),
                    }
                )

        if not missing_lines:
            return

        group = self.env.ref("hr_recruitment_automation.group_managing_partner", raise_if_not_found=False)
        if not group:
            _logger.warning("Managing Partner group not found, weekly reminder skipped.")
            return

        recipients = group.users.filtered(lambda u: u.email)
        if not recipients:
            _logger.warning("No email recipients in Managing Partner group.")
            return

        rows = "".join(
            "<tr>"
            f"<td>{line['employee'].name}</td>"
            f"<td>{line['actual']}</td>"
            f"<td>{line['expected']}</td>"
            f"<td>{line['missing']}</td>"
            "</tr>"
            for line in missing_lines
        )
        hours_table = (
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<thead><tr><th>Employee</th><th>Actual</th><th>Required</th><th>Missing</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

        template = self.env.ref(
            "hr_recruitment_automation.mail_template_weekly_hours_reminder",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Weekly reminder template not found.")
            return

        email_to = ",".join(recipients.mapped("email"))
        template.with_context(hours_table=hours_table).send_mail(
            self.env.company.id,
            force_send=True,
            email_values={"email_to": email_to},
        )
