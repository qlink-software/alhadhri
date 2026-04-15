# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# Shared Retainer helpers for BD Proposal and Engagement Letter.
# Keeps the hours, countdown, and notification logic consistent between both
# documents while respecting the current codebase split between project.project
# timesheets and qlk.project task-hour tracking.
# ------------------------------------------------------------------------------
import calendar

from odoo import _, fields, models


class BDRetainerMixin(models.AbstractModel):
    _name = "bd.retainer.mixin"
    _description = "BD Retainer Tracking Mixin"

    def _is_retainer_billing(self):
        self.ensure_one()
        if self.billing_type == "free":
            return False
        if "contract_type" in self._fields and self.contract_type == "retainer":
            return True
        return bool(getattr(self, "retainer_period", False))

    def _is_invoice_billing(self):
        self.ensure_one()
        return self.billing_type != "free"

    def _get_retainer_month_range(self):
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_end = month_start.replace(day=calendar.monthrange(today.year, today.month)[1])
        return month_start, month_end

    def _get_retainer_month_key(self):
        today = fields.Date.context_today(self)
        return today.strftime("%Y-%m")

    def _get_standard_project(self):
        self.ensure_one()
        return self.project_id if "project_id" in self._fields else self.env["project.project"]

    def _get_qlk_project(self):
        self.ensure_one()
        return self.qlk_project_id if "qlk_project_id" in self._fields else self.env["qlk.project"]

    def _get_qlk_project_ids(self, records):
        if not records or "qlk_project_id" not in getattr(records, "_fields", {}):
            return []
        return [record.qlk_project_id.id for record in records if record.qlk_project_id]

    def _get_project_timesheet_hours_map(self, project_ids, date_from=None, date_to=None):
        if not project_ids:
            return {}
        domain = [
            ("project_id", "in", project_ids),
            ("task_id", "!=", False),
        ]
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        grouped = self.env["account.analytic.line"].read_group(
            domain,
            ["unit_amount", "project_id"],
            ["project_id"],
        )
        return {
            item["project_id"][0]: item.get("unit_amount", 0.0) or 0.0
            for item in grouped
            if item.get("project_id")
        }

    def _get_qlk_project_hours_map(self, project_ids, date_from=None, date_to=None):
        if not project_ids:
            return {}
        domain = [("project_id", "in", project_ids)]
        if date_from:
            domain.append(("date_start", ">=", date_from))
        if date_to:
            domain.append(("date_start", "<=", date_to))
        grouped = self.env["qlk.task"].read_group(
            domain,
            ["hours_spent", "project_id"],
            ["project_id"],
        )
        return {
            item["project_id"][0]: item.get("hours_spent", 0.0) or 0.0
            for item in grouped
            if item.get("project_id")
        }

    def _get_record_hours(self, record, date_from=None, date_to=None):
        standard_project = record._get_standard_project()
        if standard_project:
            return record._get_project_timesheet_hours_map(
                [standard_project.id],
                date_from=date_from,
                date_to=date_to,
            ).get(standard_project.id, 0.0)
        qlk_project = record._get_qlk_project()
        if qlk_project:
            return record._get_qlk_project_hours_map(
                [qlk_project.id],
                date_from=date_from,
                date_to=date_to,
            ).get(qlk_project.id, 0.0)
        return 0.0

    def _compute_retainer_used_hours(self):
        has_qlk_project_field = "qlk_project_id" in self._fields
        standard_records = self.filtered(
            lambda rec: rec._is_retainer_billing()
            and rec.retainer_period != "annual"
            and rec._get_standard_project()
        )
        qlk_records = self.browse()
        if has_qlk_project_field:
            qlk_records = self.filtered(
                lambda rec: rec._is_retainer_billing()
                and rec.retainer_period != "annual"
                and not rec._get_standard_project()
                and rec._get_qlk_project()
            )
        standard_map = self._get_project_timesheet_hours_map(standard_records.mapped("project_id").ids)
        qlk_map = self._get_qlk_project_hours_map(self._get_qlk_project_ids(qlk_records))

        for record in self:
            if not record._is_retainer_billing():
                record.used_hours = 0.0
                continue
            if record.retainer_period == "annual" and (record.year_start_date or record.year_end_date):
                record.used_hours = record._get_record_hours(
                    record,
                    date_from=record.year_start_date,
                    date_to=record.year_end_date,
                )
                continue
            standard_project = record._get_standard_project()
            if standard_project:
                record.used_hours = standard_map.get(standard_project.id, 0.0)
                continue
            qlk_project = record._get_qlk_project()
            record.used_hours = qlk_map.get(qlk_project.id, 0.0) if qlk_project else 0.0

    def _compute_retainer_remaining_hours(self):
        for record in self:
            if not record._is_retainer_billing():
                record.remaining_hours = 0.0
                continue
            record.remaining_hours = max((record.allocated_hours or 0.0) - (record.used_hours or 0.0), 0.0)

    def _compute_retainer_monthly_used_hours(self):
        month_start, month_end = self._get_retainer_month_range()
        has_qlk_project_field = "qlk_project_id" in self._fields
        standard_records = self.filtered(
            lambda rec: rec._is_retainer_billing() and rec._get_standard_project()
        )
        qlk_records = self.browse()
        if has_qlk_project_field:
            qlk_records = self.filtered(
                lambda rec: rec._is_retainer_billing()
                and not rec._get_standard_project()
                and rec._get_qlk_project()
            )
        standard_map = self._get_project_timesheet_hours_map(
            standard_records.mapped("project_id").ids,
            date_from=month_start,
            date_to=month_end,
        )
        qlk_map = self._get_qlk_project_hours_map(
            self._get_qlk_project_ids(qlk_records),
            date_from=month_start,
            date_to=month_end,
        )
        for record in self:
            if not record._is_retainer_billing():
                record.monthly_used_hours = 0.0
                continue
            standard_project = record._get_standard_project()
            if standard_project:
                record.monthly_used_hours = standard_map.get(standard_project.id, 0.0)
                continue
            qlk_project = record._get_qlk_project()
            record.monthly_used_hours = qlk_map.get(qlk_project.id, 0.0) if qlk_project else 0.0

    def _compute_retainer_usage_visuals(self):
        for record in self:
            if not record._is_retainer_billing():
                record.retainer_usage_percent = 0.0
                record.retainer_usage_state = "normal"
                continue
            base_limit = record.allocated_hours or 0.0
            if record.retainer_period == "monthly":
                base_limit = record.monthly_hours_limit or base_limit
                consumed = record.monthly_used_hours
            else:
                consumed = record.used_hours
            if not base_limit:
                record.retainer_usage_percent = 0.0
                record.retainer_usage_state = "normal"
                continue
            percent = (consumed / base_limit) * 100.0
            record.retainer_usage_percent = min(max(percent, 0.0), 100.0)
            if percent > 90.0:
                record.retainer_usage_state = "danger"
            elif percent >= 70.0:
                record.retainer_usage_state = "warning"
            else:
                record.retainer_usage_state = "success"

    def _get_retainer_notification_users(self):
        self.ensure_one()
        users = self.env["res.users"]
        xmlids = (
            "qlk_management.bd_manager_group",
            "qlk_management.bd_assistant_manager_group",
            "account.group_account_user",
        )
        for xmlid in xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                users |= group.users
        if getattr(self, "reviewer_id", False):
            users |= self.reviewer_id
        if getattr(self, "lawyer_user_id", False):
            users |= self.lawyer_user_id
        return users.filtered(lambda user: user.active and not user.share)

    def _build_retainer_exceeded_message(self):
        self.ensure_one()
        partner_name = self.partner_id.display_name if self.partner_id else self.display_name
        limit = self.monthly_hours_limit or self.allocated_hours or 0.0
        return _(
            "Monthly Retainer Hours Exceeded for %(client)s. Used Hours: %(used)s / Limit: %(limit)s"
        ) % {
            "client": partner_name,
            "used": f"{(self.monthly_used_hours or 0.0):.2f}",
            "limit": f"{limit:.2f}",
        }

    def _notify_retainer_exceeded(self):
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for record in self:
            users = record._get_retainer_notification_users()
            message = record._build_retainer_exceeded_message()
            record.message_post(
                body=message,
                partner_ids=users.mapped("partner_id").ids,
            )
            if not activity_type:
                continue
            summary = _("Monthly Retainer Hours Exceeded for %s") % (
                record.partner_id.display_name if record.partner_id else record.display_name,
            )
            for user in users:
                record.activity_schedule(
                    activity_type.id,
                    user_id=user.id,
                    summary=summary,
                    note=message,
                )

    def _process_retainer_notifications(self):
        month_key = self._get_retainer_month_key()
        for record in self:
            if not record._is_retainer_billing() or record.retainer_period != "monthly":
                continue
            if record.exception_approved:
                continue
            if getattr(record, "state", False) in {"rejected", "cancelled"}:
                continue
            if not (record._get_standard_project() or record._get_qlk_project()):
                continue
            limit = record.monthly_hours_limit or record.allocated_hours or 0.0
            if limit <= 0:
                continue
            if record.monthly_used_hours <= limit:
                continue
            if record.last_retainer_alert_key == month_key:
                continue
            record._notify_retainer_exceeded()
            record.sudo().write({"last_retainer_alert_key": month_key})
