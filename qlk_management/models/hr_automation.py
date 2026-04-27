# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models


class QlkHrAutomation(models.AbstractModel):
    _name = "qlk.hr.automation"
    _description = "QLK HR Automation Service"

    REQUIRED_HOURS_PER_DAY = 8.0

    # ------------------------------------------------------------------------------
    # هذه الدالة تحسب ساعات العمل المطلوبة بين تاريخين مع استبعاد عطلة نهاية الأسبوع.
    # ------------------------------------------------------------------------------
    def _required_hours_between(self, date_from, date_to):
        if not date_from or not date_to or date_to < date_from:
            return 0.0
        days_count = (date_to - date_from).days + 1
        total = 0.0
        for offset in range(days_count):
            current_day = date_from + timedelta(days=offset)
            if current_day.weekday() < 5:
                total += self.REQUIRED_HOURS_PER_DAY
        return total

    # ------------------------------------------------------------------------------
    # هذه الدالة تجمع ساعات الحضور الفعلية للموظفين خلال نافذة زمنية محددة.
    # ------------------------------------------------------------------------------
    def _attendance_hours_map(self, employee_ids, datetime_from, datetime_to):
        attendance_model = self.env["hr.attendance"]
        if not employee_ids:
            return {}
        grouped = attendance_model.read_group(
            [
                ("employee_id", "in", employee_ids),
                ("check_in", ">=", datetime_from),
                ("check_in", "<=", datetime_to),
            ],
            ["employee_id", "worked_hours"],
            ["employee_id"],
            lazy=False,
        )
        return {
            item["employee_id"][0]: float(item.get("worked_hours") or 0.0)
            for item in grouped
            if item.get("employee_id")
        }

    # ------------------------------------------------------------------------------
    # هذه الدالة تبني سطور الموظفين الذين لديهم نقص في الساعات الأسبوعية.
    # ------------------------------------------------------------------------------
    def _build_missing_hours_rows(self, employees, until_date):
        if not employees:
            return []

        week_start = until_date - timedelta(days=until_date.weekday())
        start_dt = datetime.combine(week_start, time.min)
        end_dt = datetime.combine(until_date, time.max)
        required_hours = self._required_hours_between(week_start, until_date)
        hours_map = self._attendance_hours_map(employees.ids, start_dt, end_dt)

        rows = []
        for employee in employees:
            actual_hours = float(hours_map.get(employee.id, 0.0))
            missing_hours = max(required_hours - actual_hours, 0.0)
            if missing_hours <= 0:
                continue
            rows.append(
                {
                    "employee": employee,
                    "actual_hours": round(actual_hours, 2),
                    "required_hours": round(required_hours, 2),
                    "missing_hours": round(missing_hours, 2),
                }
            )
        return rows

    # ------------------------------------------------------------------------------
    # هذه الدالة تسترجع مستخدمي مجموعة MP لإرسال تنبيه الساعات الأسبوعية لهم.
    # ------------------------------------------------------------------------------
    def _get_mp_users(self):
        mp_group = self.env.ref("qlk_management.group_pre_litigation_manager", raise_if_not_found=False)
        if not mp_group:
            return self.env["res.users"]
        return mp_group.users.filtered(lambda user: user.active and (user.partner_id.email or user.email))

    # ------------------------------------------------------------------------------
    # هذا الكرون لإرسال تنبيه الساعات الأسبوعية للـ MP كل يوم أربعاء.
    # ------------------------------------------------------------------------------
    @api.model
    def cron_send_weekly_hours_reminder(self):
        today = fields.Date.context_today(self)
        # weekday(): Monday=0 ... Wednesday=2
        if today.weekday() != 2:
            return True

        employees = self.env["hr.employee"].search(
            [
                ("active", "=", True),
                ("user_id", "!=", False),
            ]
        )
        missing_rows = self._build_missing_hours_rows(employees, today)
        if not missing_rows:
            return True

        mp_users = self._get_mp_users()
        if not mp_users:
            return True

        lines = []
        for row in missing_rows:
            lines.append(
                "<li>%s: %.2f / %.2f (Missing %.2f)</li>"
                % (
                    row["employee"].name,
                    row["actual_hours"],
                    row["required_hours"],
                    row["missing_hours"],
                )
            )
        missing_lines_html = "<ul>%s</ul>" % "".join(lines)

        template = self.env.ref("qlk_management.mail_template_weekly_hours_reminder_mp", raise_if_not_found=False)
        if not template:
            return True

        week_start = today - timedelta(days=today.weekday())
        week_label = "%s - %s" % (week_start, today)

        # هذه الرسالة تُبنى ديناميكيًا وتُرسل عبر mail.template مع قائمة النقص الفعلية.
        subject = _("Weekly Working Hours Reminder - %s") % week_label
        body_html = (
            "<div>"
            "<p>Dear MP,</p>"
            "<p>The following employees have missing working hours for week <strong>%s</strong>:</p>"
            "%s"
            "<p>Regards,<br/>QLK HR Automation</p>"
            "</div>"
        ) % (week_label, missing_lines_html)

        for user in mp_users:
            email_to = user.partner_id.email or user.email
            if not email_to:
                continue
            template.send_mail(
                user.id,
                force_send=False,
                email_values={
                    "email_to": email_to,
                    "subject": subject,
                    "body_html": body_html,
                },
            )

        return True
