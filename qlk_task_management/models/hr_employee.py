# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class HREmployee(models.Model):
    _inherit = "hr.employee"

    task_ids = fields.One2many("qlk.task", "employee_id", string="Tasks")
    task_hours_total = fields.Float(
        string="Approved Hours (All Time)",
        compute="_compute_task_metrics",
    )
    task_hours_month = fields.Float(
        string="Approved Hours (This Month)",
        compute="_compute_task_metrics",
    )
    task_hours_week = fields.Float(
        string="Approved Hours (This Week)",
        compute="_compute_task_metrics",
    )
    task_waiting_count = fields.Integer(
        string="Tasks Awaiting Approval",
        compute="_compute_task_metrics",
    )
    task_rejected_count = fields.Integer(
        string="Tasks Returned",
        compute="_compute_task_metrics",
    )

    def action_open_employee_tasks(self):
        self.ensure_one()
        action = self.env.ref("qlk_task_management.action_qlk_task_all").read()[0]
        context = action.get("context") or {}
        if isinstance(context, str):
            context = safe_eval(context)
        action["context"] = {
            **context,
            "default_employee_id": self.id,
            "search_default_group_month": 1,
        }
        action["domain"] = [("employee_id", "=", self.id)]
        return action

    def _compute_task_metrics(self):
        Task = self.env["qlk.task"]
        employees = self.filtered(lambda emp: emp.id)
        if not employees:
            for employee in self:
                employee.task_hours_total = 0.0
                employee.task_hours_month = 0.0
                employee.task_hours_week = 0.0
                employee.task_waiting_count = 0
                employee.task_rejected_count = 0
            return

        employee_ids = employees.ids
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=1, days=-1)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        def aggregate(domain):
            grouped = Task.read_group(domain, ["hours_spent", "employee_id"], ["employee_id"])
            mapping = {employee_id: 0.0 for employee_id in employee_ids}
            for entry in grouped:
                employee_ref = entry.get("employee_id")
                if employee_ref:
                    mapping[employee_ref[0]] = entry.get("hours_spent", 0.0)
            return mapping

        base_domain = [("employee_id", "in", employee_ids), ("approval_state", "=", "approved")]
        month_domain = base_domain + [("date_start", ">=", month_start), ("date_start", "<=", month_end)]
        week_domain = base_domain + [("date_start", ">=", week_start), ("date_start", "<=", week_end)]

        total_map = aggregate(base_domain)
        month_map = aggregate(month_domain)
        week_map = aggregate(week_domain)

        waiting_grouped = Task.read_group(
            [("employee_id", "in", employee_ids), ("approval_state", "=", "waiting")],
            ["employee_id"],
            ["employee_id"],
        )
        waiting_map = {employee_id: 0 for employee_id in employee_ids}
        for entry in waiting_grouped:
            ref = entry.get("employee_id")
            if ref:
                waiting_map[ref[0]] = entry.get("employee_id_count", 0)

        rejected_grouped = Task.read_group(
            [("employee_id", "in", employee_ids), ("approval_state", "=", "rejected")],
            ["employee_id"],
            ["employee_id"],
        )
        rejected_map = {employee_id: 0 for employee_id in employee_ids}
        for entry in rejected_grouped:
            ref = entry.get("employee_id")
            if ref:
                rejected_map[ref[0]] = entry.get("employee_id_count", 0)

        for employee in self:
            if not employee.id:
                employee.task_hours_total = 0.0
                employee.task_hours_month = 0.0
                employee.task_hours_week = 0.0
                employee.task_waiting_count = 0
                employee.task_rejected_count = 0
                continue

            employee.task_hours_total = total_map.get(employee.id, 0.0)
            employee.task_hours_month = month_map.get(employee.id, 0.0)
            employee.task_hours_week = week_map.get(employee.id, 0.0)
            employee.task_waiting_count = waiting_map.get(employee.id, 0)
            employee.task_rejected_count = rejected_map.get(employee.id, 0)
