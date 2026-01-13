# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class ExecutiveDashboard(models.AbstractModel):
    _name = "qlk.executive.dashboard"
    _description = "Executive Dashboard Service"

    def _ensure_access(self):
        user = self.env.user
        if not (
            user.has_group("qlk_executive_dashboard.group_qlk_manager")
            or user.has_group("qlk_executive_dashboard.group_qlk_assistant_manager")
        ):
            raise AccessError(_("You do not have access to the executive dashboard."))

    def _model(self, model_name):
        return self.env[model_name] if model_name in self.env else None

    def _field_exists(self, model, field_name):
        return bool(model) and field_name in model._fields

    def _read_group(self, model, domain, fields, groupby, **kwargs):
        if not model:
            return []
        try:
            return model.read_group(domain, fields, groupby, **kwargs)
        except Exception:
            return []

    def _count(self, model_name, domain):
        Model = self._model(model_name)
        if not Model:
            return 0
        result = self._read_group(Model, domain, ["id"], [])
        if not result:
            return 0
        row = result[0]
        return row.get("__count") or row.get("id_count") or row.get("id") or 0

    def _sum(self, model_name, domain, field_name):
        Model = self._model(model_name)
        if not Model or not self._field_exists(Model, field_name):
            return 0.0
        result = self._read_group(Model, domain, [field_name], [])
        if not result:
            return 0.0
        return result[0].get(field_name) or 0.0

    def _selection_label(self, model, field_name, value):
        field = model._fields.get(field_name)
        if not field or not getattr(field, "selection", None):
            return value
        return dict(field.selection).get(value, value)

    def _group_counts(self, model_name, domain, groupby_field, limit=10):
        Model = self._model(model_name)
        if not Model or not self._field_exists(Model, groupby_field):
            return []
        grouped = self._read_group(Model, domain, [groupby_field], [groupby_field], limit=limit)
        results = []
        for entry in grouped:
            raw_value = entry.get(groupby_field)
            if not raw_value:
                continue
            if isinstance(raw_value, tuple):
                label = raw_value[1]
                value = raw_value[0]
            else:
                label = self._selection_label(Model, groupby_field, raw_value)
                value = raw_value
            count = (
                entry.get(f"{groupby_field}_count")
                or entry.get("__count")
                or entry.get("id_count")
                or 0
            )
            results.append(
                {
                    "label": label,
                    "value": count,
                    "domain": [(groupby_field, "=", value)],
                }
            )
        return results

    def _date_group_counts(self, model_name, domain, date_field, groupby_unit="day"):
        Model = self._model(model_name)
        if not Model or not self._field_exists(Model, date_field):
            return []
        groupby = f"{date_field}:{groupby_unit}"
        grouped = self._read_group(Model, domain, [date_field], [groupby])
        results = []
        for entry in grouped:
            label = entry.get(groupby) or entry.get(date_field)
            if not label:
                continue
            count = entry.get("__count") or entry.get("id_count") or 0
            results.append({"label": label, "value": count})
        return results

    def _month_ranges(self, months=6):
        today = fields.Date.context_today(self)
        start_month = today.replace(day=1) - relativedelta(months=months - 1)
        ranges = []
        for i in range(months):
            current = start_month + relativedelta(months=i)
            start = current
            end = current + relativedelta(months=1, days=-1)
            label = current.strftime("%Y-%m")
            ranges.append((label, fields.Date.to_string(start), fields.Date.to_string(end)))
        return ranges

    def _aggregate_monthly_sum(self, model_name, domain, date_field, value_field, months=6):
        results = []
        for label, date_from, date_to in self._month_ranges(months=months):
            local_domain = list(domain)
            local_domain += [
                (date_field, ">=", date_from),
                (date_field, "<=", date_to),
            ]
            value = self._sum(model_name, local_domain, value_field)
            results.append({"label": label, "value": value})
        return results

    def _scope_domain(self, model_name):
        user = self.env.user
        if user.has_group("qlk_executive_dashboard.group_qlk_manager"):
            return []
        if not user.has_group("qlk_executive_dashboard.group_qlk_assistant_manager"):
            return []

        Model = self._model(model_name)
        if not Model:
            return []

        employee = user.employee_id if "employee_id" in user._fields else False
        employee_ids = user.employee_ids.ids if "employee_ids" in user._fields else []
        candidates = [
            ("user_id", user.id),
            ("assigned_user_id", user.id),
            ("owner_id", user.id),
            ("responsible_id", user.id),
            ("invoice_user_id", user.id),
        ]
        if employee:
            candidates.append(("employee_id", employee.id))
        if employee_ids:
            candidates.append(("employee_ids", employee_ids))
            candidates.append(("assigned_employee_ids", employee_ids))

        for field_name, value in candidates:
            if not self._field_exists(Model, field_name):
                continue
            operator = "in" if isinstance(value, list) else "="
            return [(field_name, operator, value)]
        return []

    def _status_level(self, value, warn_at=1, critical_at=5):
        if value >= critical_at:
            return "critical"
        if value >= warn_at:
            return "warning"
        return "ok"

    def _session_model(self):
        for model_name in ("qlk.session", "qlk.hearing"):
            if model_name in self.env:
                return model_name
        return None

    def _session_date_field(self, model):
        for name in ("date", "session_date", "hearing_date", "start_date"):
            if self._field_exists(model, name):
                return name
        return None

    @api.model
    def get_dashboard_data(self):
        self._ensure_access()
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        user = self.env.user

        palette = {
            "primary": "#0B2C3F",
            "accent": "#C9A56A",
            "muted": "#1C3D4B",
            "success": "#2C8C6A",
            "warning": "#D87A4A",
            "danger": "#B83A3A",
        }

        litigation_domain = self._scope_domain("qlk.case")
        case_report_model = "qlk.executive.case.report" if not litigation_domain else "qlk.case"
        case_report_domain = litigation_domain

        active_domain = list(litigation_domain)
        Case = self._model("qlk.case")
        if Case and self._field_exists(Case, "state"):
            active_domain.append(("state", "not in", ["done", "closed", "cancel", "cancelled", "rejected"]))
        elif Case and self._field_exists(Case, "status"):
            active_domain.append(("status", "not in", ["closed", "cancelled", "rejected"]))

        total_active_cases = self._count("qlk.case", active_domain)

        litigation_flow = self._group_counts(
            case_report_model,
            case_report_domain,
            "litigation_flow",
            limit=4,
        )

        court_type_field = None
        if case_report_model == "qlk.executive.case.report":
            court_type_field = "case_group_id"
        else:
            for candidate in ("court_type", "case_group", "case_group_id"):
                if Case and self._field_exists(Case, candidate):
                    court_type_field = candidate
                    break

        cases_by_court = (
            self._group_counts(case_report_model, case_report_domain, court_type_field, limit=12)
            if court_type_field
            else []
        )
        cases_by_status = self._group_counts(case_report_model, case_report_domain, "status", limit=12)

        session_model_name = self._session_model()
        session_model = self._model(session_model_name) if session_model_name else None
        session_date_field = self._session_date_field(session_model) if session_model else None
        session_domain = self._scope_domain(session_model_name) if session_model_name else []

        overdue_sessions = 0
        upcoming_7 = 0
        upcoming_30 = 0
        sessions_timeline = []
        overdue_domain = []
        upcoming_7_domain = []
        upcoming_30_domain = []
        if session_model and session_date_field:
            session_open_domain = list(session_domain)
            if self._field_exists(session_model, "state"):
                session_open_domain.append(("state", "not in", ["done", "cancel", "cancelled"]))
            overdue_domain = list(session_open_domain) + [(session_date_field, "<", today)]
            upcoming_7_domain = list(session_open_domain) + [
                (session_date_field, ">=", today),
                (session_date_field, "<=", today + timedelta(days=7)),
            ]
            upcoming_30_domain = list(session_open_domain) + [
                (session_date_field, ">=", today),
                (session_date_field, "<=", today + timedelta(days=30)),
            ]
            overdue_sessions = self._count(session_model_name, overdue_domain)
            upcoming_7 = self._count(session_model_name, upcoming_7_domain)
            upcoming_30 = self._count(session_model_name, upcoming_30_domain)
            sessions_timeline = self._date_group_counts(session_model_name, upcoming_30_domain, session_date_field)

        execution_model = self._model("court.execution.case")
        execution_domain = self._scope_domain("court.execution.case")
        execution_cases = self._count("court.execution.case", execution_domain)
        execution_action = (
            self._action_window("court.execution.case", execution_domain, _("Execution Cases"))
            if execution_model
            else None
        )

        claimed_total = self._sum("qlk.case", litigation_domain, "case_value")

        move_model = self._model("account.move")
        collected_total = 0.0
        collected_action = None
        if move_model and self._field_exists(move_model, "case_id"):
            case_invoice_domain = [
                ("state", "=", "posted"),
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("case_id", "!=", False),
            ]
            invoiced_total = self._sum("account.move", case_invoice_domain, "amount_total")
            residual_total = self._sum("account.move", case_invoice_domain, "amount_residual")
            collected_total = max(invoiced_total - residual_total, 0.0)
            collected_action = self._action_window("account.move", case_invoice_domain, _("Collected Amounts"))

        litigation_kpis = [
            {
                "label": _("Total Active Cases"),
                "value": total_active_cases,
                "status": self._status_level(total_active_cases, warn_at=50, critical_at=150),
                "action": self._action_window("qlk.case", active_domain, _("Active Cases")),
            },
            {
                "label": _("Execution Cases"),
                "value": execution_cases,
                "status": self._status_level(execution_cases, warn_at=10, critical_at=30),
                "action": execution_action,
            },
            {
                "label": _("Overdue Sessions"),
                "value": overdue_sessions,
                "status": self._status_level(overdue_sessions, warn_at=1, critical_at=5),
                "action": self._action_window(session_model_name, overdue_domain, _("Overdue Sessions")) if session_model_name else None,
            },
            {
                "label": _("Upcoming Sessions"),
                "value": upcoming_30,
                "status": self._status_level(upcoming_30, warn_at=10, critical_at=30),
                "action": self._action_window(session_model_name, upcoming_30_domain, _("Upcoming Sessions")) if session_model_name else None,
            },
            {
                "label": _("Total Claimed"),
                "value": claimed_total,
                "status": "ok",
                "action": self._action_window("qlk.case", litigation_domain, _("Claimed Amounts")),
            },
            {
                "label": _("Total Collected"),
                "value": collected_total,
                "status": "ok",
                "action": collected_action,
            },
        ]

        litigation_charts = {}
        if cases_by_court:
            litigation_charts["cases_by_court"] = self._chart_bar(
                _("Cases by Court Type"), cases_by_court, palette.get("accent")
            )
        if cases_by_status:
            litigation_charts["cases_by_status"] = self._chart_doughnut(
                _("Cases by Status"), cases_by_status
            )
        if sessions_timeline:
            litigation_charts["sessions_timeline"] = self._chart_line(
                _("Upcoming Sessions (30 Days)"), sessions_timeline, palette.get("primary")
            )

        finance_scope = self._scope_domain("qlk.executive.finance.report")
        revenue_domain = finance_scope + [("move_type", "in", ["out_invoice", "out_refund"])]
        expense_domain = finance_scope + [("move_type", "in", ["in_invoice", "in_refund"])]
        unpaid_domain = revenue_domain + [("amount_residual", ">", 0)]
        overdue_domain = unpaid_domain + [("invoice_date_due", "<", today)]

        receivables = self._sum("qlk.executive.finance.report", revenue_domain, "amount_residual")
        payables = self._sum("qlk.executive.finance.report", expense_domain, "amount_residual")
        invoiced = self._sum("qlk.executive.finance.report", revenue_domain, "amount_total")
        collected = max(invoiced - receivables, 0.0)
        expenses = self._sum("qlk.executive.finance.report", expense_domain, "amount_total")
        net_profit = invoiced - expenses

        unpaid_invoices = self._count("qlk.executive.finance.report", unpaid_domain)
        overdue_invoices = self._count("qlk.executive.finance.report", overdue_domain)

        invoice_date_field = "invoice_date" if self._field_exists(self._model("account.move"), "invoice_date") else "date"
        month_start = today.replace(day=1)
        last_month_start = (month_start - relativedelta(months=1)).replace(day=1)
        last_month_end = month_start - timedelta(days=1)

        this_month_domain = list(revenue_domain) + [
            (invoice_date_field, ">=", fields.Date.to_string(month_start)),
            (invoice_date_field, "<=", fields.Date.to_string(today)),
        ]
        last_month_domain = list(revenue_domain) + [
            (invoice_date_field, ">=", fields.Date.to_string(last_month_start)),
            (invoice_date_field, "<=", fields.Date.to_string(last_month_end)),
        ]

        revenue_this_month = self._sum("qlk.executive.finance.report", this_month_domain, "amount_total")
        revenue_last_month = self._sum("qlk.executive.finance.report", last_month_domain, "amount_total")

        legal_fee_domain = list(revenue_domain)
        if move_model and self._field_exists(move_model, "case_id"):
            legal_fee_domain.append(("case_id", "!=", False))
        outstanding_fees = self._sum("account.move", legal_fee_domain, "amount_residual")

        finance_kpis = [
            {
                "label": _("Total Receivables"),
                "value": receivables,
                "status": self._status_level(receivables, warn_at=50000, critical_at=150000),
                "action": self._action_window("account.move", revenue_domain, _("Customer Invoices")),
            },
            {
                "label": _("Total Payables"),
                "value": payables,
                "status": self._status_level(payables, warn_at=50000, critical_at=150000),
                "action": self._action_window("account.move", expense_domain, _("Vendor Bills")),
            },
            {
                "label": _("Total Revenue"),
                "value": invoiced,
                "status": "ok",
                "action": self._action_window("account.move", revenue_domain, _("Customer Invoices")),
            },
            {
                "label": _("Unpaid Invoices"),
                "value": unpaid_invoices,
                "status": self._status_level(unpaid_invoices, warn_at=10, critical_at=30),
                "action": self._action_window("account.move", unpaid_domain, _("Unpaid Invoices")),
            },
            {
                "label": _("Overdue Invoices"),
                "value": overdue_invoices,
                "status": self._status_level(overdue_invoices, warn_at=5, critical_at=15),
                "action": self._action_window("account.move", overdue_domain, _("Overdue Invoices")),
            },
            {
                "label": _("Expenses"),
                "value": expenses,
                "status": self._status_level(expenses, warn_at=50000, critical_at=150000),
                "action": self._action_window("account.move", expense_domain, _("Expenses")),
            },
            {
                "label": _("Net Profit"),
                "value": net_profit,
                "status": "ok",
                "action": self._action_window("account.move", revenue_domain, _("Net Profit")),
            },
            {
                "label": _("Outstanding Legal Fees"),
                "value": outstanding_fees,
                "status": self._status_level(outstanding_fees, warn_at=25000, critical_at=80000),
                "action": self._action_window("account.move", legal_fee_domain, _("Outstanding Fees")),
            },
            {
                "label": _("Monthly Revenue (This Month)"),
                "value": revenue_this_month,
                "status": "ok",
                "action": self._action_window("account.move", this_month_domain, _("Monthly Revenue")),
            },
            {
                "label": _("Monthly Revenue (Last Month)"),
                "value": revenue_last_month,
                "status": "ok",
                "action": self._action_window("account.move", last_month_domain, _("Last Month Revenue")),
            },
        ]

        revenue_by_month = self._aggregate_monthly_sum(
            "qlk.executive.finance.report", revenue_domain, invoice_date_field, "amount_total", months=6
        )
        finance_charts = {}
        if revenue_by_month:
            finance_charts["revenue_by_month"] = self._chart_line(
                _("Revenue by Month"), revenue_by_month, palette.get("accent")
            )

        if move_model and self._field_exists(move_model, "case_id"):
            fees_by_case = self._group_sums(
                "account.move", legal_fee_domain, "case_id", "amount_total", limit=8
            )
            if fees_by_case:
                finance_charts["fees_by_case"] = self._chart_bar(
                    _("Legal Fees by Case"), fees_by_case, palette.get("primary")
                )

        paid_vs_unpaid = self._group_counts("qlk.executive.finance.report", revenue_domain, "payment_state", limit=5)
        if paid_vs_unpaid:
            finance_charts["paid_vs_unpaid"] = self._chart_doughnut(
                _("Paid vs Unpaid Invoices"), paid_vs_unpaid
            )

        hr_domain = self._scope_domain("hr.employee")
        total_employees = self._count("hr.employee", hr_domain)
        active_employees = 0
        inactive_employees = 0
        if self._field_exists(self._model("hr.employee"), "active"):
            active_employees = self._count("hr.employee", hr_domain + [("active", "=", True)])
            inactive_employees = self._count("hr.employee", hr_domain + [("active", "=", False)])

        approved_leaves = self._count("hr.leave", [("state", "=", "validate")])
        pending_leaves = self._count("hr.leave", [("state", "in", ["confirm", "validate1"])])

        start_dt = fields.Datetime.to_string(fields.Datetime.combine(today, fields.Datetime.min.time()))
        end_dt = fields.Datetime.to_string(fields.Datetime.combine(today + timedelta(days=1), fields.Datetime.min.time()))
        attendance_today = 0
        attendance_action = None
        if "hr.attendance" in self.env:
            attendance_domain = [("check_in", ">=", start_dt), ("check_in", "<", end_dt)]
            attendance_today = self._count("hr.attendance", attendance_domain)
            attendance_action = self._action_window("hr.attendance", attendance_domain, _("Attendance"))

        payroll_summary = 0.0
        payroll_action = None
        if "hr.payslip" in self.env:
            payslip_domain = [
                ("date_from", ">=", fields.Date.to_string(month_start)),
                ("date_to", "<=", fields.Date.to_string(today)),
            ]
            payslip_model = self._model("hr.payslip")
            amount_field = None
            for candidate in ("net_wage", "net_salary", "amount", "amount_total"):
                if self._field_exists(payslip_model, candidate):
                    amount_field = candidate
                    break
            if amount_field:
                payroll_summary = self._sum("hr.payslip", payslip_domain, amount_field)
            else:
                payroll_summary = self._count("hr.payslip", payslip_domain)
            payroll_action = self._action_window("hr.payslip", payslip_domain, _("Payroll"))

        expiring_contracts = 0
        expiring_action = None
        if "hr.contract" in self.env:
            contract_domain = [
                ("date_end", ">=", fields.Date.to_string(today)),
                ("date_end", "<=", fields.Date.to_string(today + timedelta(days=30))),
            ]
            expiring_contracts = self._count("hr.contract", contract_domain)
            expiring_action = self._action_window("hr.contract", contract_domain, _("Expiring Contracts"))

        expiring_procurations = 0
        if "qlk.procuration" in self.env:
            procuration_domain = [
                ("expiry_date", ">=", fields.Date.to_string(today)),
                ("expiry_date", "<=", fields.Date.to_string(today + timedelta(days=30))),
            ]
            expiring_procurations = self._count("qlk.procuration", procuration_domain)
            if not expiring_action:
                expiring_action = self._action_window("qlk.procuration", procuration_domain, _("Expiring Procurations"))

        expiring_total = expiring_contracts + expiring_procurations

        hr_kpis = [
            {
                "label": _("Total Employees"),
                "value": total_employees,
                "status": "ok",
                "action": self._action_window("hr.employee", hr_domain, _("Employees")),
            },
            {
                "label": _("Active Employees"),
                "value": active_employees,
                "status": "ok",
                "action": self._action_window("hr.employee", hr_domain + [("active", "=", True)], _("Active Employees")),
            },
            {
                "label": _("Inactive Employees"),
                "value": inactive_employees,
                "status": self._status_level(inactive_employees, warn_at=1, critical_at=5),
                "action": self._action_window("hr.employee", hr_domain + [("active", "=", False)], _("Inactive Employees")),
            },
            {
                "label": _("Attendance Today"),
                "value": attendance_today,
                "status": "ok",
                "action": attendance_action,
            },
            {
                "label": _("Approved Leaves"),
                "value": approved_leaves,
                "status": "ok",
                "action": self._action_window("hr.leave", [("state", "=", "validate")], _("Approved Leaves")),
            },
            {
                "label": _("Pending Leaves"),
                "value": pending_leaves,
                "status": self._status_level(pending_leaves, warn_at=1, critical_at=5),
                "action": self._action_window("hr.leave", [("state", "in", ["confirm", "validate1"])], _("Pending Leaves")),
            },
            {
                "label": _("Payroll Summary"),
                "value": payroll_summary,
                "status": "ok",
                "action": payroll_action,
            },
            {
                "label": _("Expiring Contracts / QID"),
                "value": expiring_total,
                "status": self._status_level(expiring_total, warn_at=1, critical_at=5),
                "action": expiring_action,
            },
        ]

        hr_charts = {}
        dept_breakdown = self._group_counts("hr.employee", hr_domain, "department_id", limit=8)
        if dept_breakdown:
            hr_charts["employees_by_department"] = self._chart_bar(
                _("Employees by Department"), dept_breakdown, palette.get("accent")
            )
        position_breakdown = self._group_counts("hr.employee", hr_domain, "job_id", limit=8)
        if position_breakdown:
            hr_charts["employees_by_position"] = self._chart_bar(
                _("Employees by Position"), position_breakdown, palette.get("primary")
            )
        leave_breakdown = self._group_counts("hr.leave", [], "state", limit=5)
        if leave_breakdown:
            hr_charts["leave_status"] = self._chart_doughnut(
                _("Leaves Status"), leave_breakdown
            )

        approvals_domain = []
        if "approval.request" in self.env and self._field_exists(self._model("approval.request"), "request_owner_id"):
            if user.has_group("qlk_executive_dashboard.group_qlk_assistant_manager"):
                approvals_domain = [("request_owner_id", "=", user.id)]

        pending_states = ["pending", "new"]
        pending_approvals = self._count("approval.request", approvals_domain + [("state", "in", pending_states)])
        approved_today = 0
        rejected_requests = self._count("approval.request", approvals_domain + [("state", "in", ["refused", "cancel"])])

        approval_model = self._model("approval.request")
        if approval_model and self._field_exists(approval_model, "date_approve"):
            approved_today = self._count(
                "approval.request",
                approvals_domain + [("date_approve", ">=", today), ("state", "=", "approved")],
            )
        elif approval_model and self._field_exists(approval_model, "write_date"):
            approved_today = self._count(
                "approval.request",
                approvals_domain + [("write_date", ">=", today), ("state", "=", "approved")],
            )

        delayed_approvals = 0
        deadline_field = self._approval_deadline_field()
        if deadline_field:
            delayed_approvals = self._count(
                "approval.request",
                approvals_domain
                + [(deadline_field, "<", fields.Date.context_today(self)), ("state", "in", pending_states)],
            )

        approvals_kpis = [
            {
                "label": _("Pending Approvals"),
                "value": pending_approvals,
                "status": self._status_level(pending_approvals, warn_at=1, critical_at=5),
                "action": self._action_window(
                    "approval.request",
                    approvals_domain + [("state", "in", pending_states)],
                    _("Pending Approvals"),
                ),
            },
            {
                "label": _("Approved Today"),
                "value": approved_today,
                "status": "ok",
                "action": self._action_window(
                    "approval.request",
                    approvals_domain + [("state", "=", "approved")],
                    _("Approved Today"),
                ),
            },
            {
                "label": _("Delayed Approvals"),
                "value": delayed_approvals,
                "status": self._status_level(delayed_approvals, warn_at=1, critical_at=5),
                "action": self._action_window(
                    "approval.request",
                    approvals_domain
                    + [(deadline_field, "<", fields.Date.context_today(self)), ("state", "in", pending_states)],
                    _("Delayed Approvals"),
                )
                if deadline_field
                else None,
            },
            {
                "label": _("Rejected Requests"),
                "value": rejected_requests,
                "status": self._status_level(rejected_requests, warn_at=1, critical_at=3),
                "action": self._action_window(
                    "approval.request",
                    approvals_domain + [("state", "in", ["refused", "cancel"])],
                    _("Rejected Requests"),
                ),
            },
        ]

        approvals_by_model = self._group_counts("approval.request", approvals_domain, "res_model", limit=8)
        approvals_charts = {}
        if approvals_by_model:
            approvals_charts["approvals_by_model"] = self._chart_bar(
                _("Approvals by Model"), approvals_by_model, palette.get("accent")
            )

        pending_list = self._approval_list(approvals_domain + [("state", "in", pending_states)])
        delayed_list = self._approval_delayed_list(pending_states, approvals_domain=approvals_domain)

        return {
            "palette": palette,
            "litigation": {
                "kpis": litigation_kpis,
                "pre_litigation_vs_litigation": litigation_flow,
                "case_status": cases_by_status,
                "cases_by_court": cases_by_court,
                "charts": litigation_charts,
            },
            "finance": {
                "kpis": finance_kpis,
                "charts": finance_charts,
            },
            "hr": {
                "kpis": hr_kpis,
                "charts": hr_charts,
            },
            "approvals": {
                "kpis": approvals_kpis,
                "charts": approvals_charts,
                "lists": {
                    "pending": pending_list,
                    "delayed": delayed_list,
                },
            },
        }

    def _approval_list(self, domain, limit=None):
        if "approval.request" not in self.env:
            return []
        Approval = self.env["approval.request"]
        fields_list = ["name", "request_owner_id", "create_date", "state"]
        data = Approval.search_read(domain, fields_list, order="create_date desc", limit=limit)
        results = []
        for row in data:
            results.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "owner": row.get("request_owner_id")[1] if row.get("request_owner_id") else "",
                    "date": row.get("create_date"),
                }
            )
        return results

    def _approval_deadline_field(self):
        Approval = self._model("approval.request")
        if not Approval:
            return None
        for candidate in ("date_deadline", "deadline", "request_deadline"):
            if self._field_exists(Approval, candidate):
                return candidate
        return None

    def _approval_delayed_list(self, pending_states, approvals_domain=None, limit=None):
        if "approval.request" not in self.env:
            return []
        Approval = self.env["approval.request"]
        deadline_field = self._approval_deadline_field()
        if not deadline_field:
            return []
        approvals_domain = approvals_domain or []
        domain = approvals_domain + [
            (deadline_field, "<", fields.Date.context_today(self)),
            ("state", "in", pending_states),
        ]
        fields_list = ["name", "request_owner_id", deadline_field, "state"]
        data = Approval.search_read(domain, fields_list, order=f"{deadline_field} asc", limit=limit)
        results = []
        for row in data:
            results.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "owner": row.get("request_owner_id")[1] if row.get("request_owner_id") else "",
                    "date": row.get(deadline_field),
                }
            )
        return results

    def _group_sums(self, model_name, domain, groupby_field, sum_field, limit=8):
        Model = self._model(model_name)
        if not Model or not self._field_exists(Model, groupby_field) or not self._field_exists(Model, sum_field):
            return []
        grouped = self._read_group(Model, domain, [sum_field, groupby_field], [groupby_field], limit=limit)
        results = []
        for entry in grouped:
            raw_value = entry.get(groupby_field)
            if not raw_value:
                continue
            if isinstance(raw_value, tuple):
                label = raw_value[1]
                value = raw_value[0]
            else:
                label = raw_value
                value = raw_value
            total = entry.get(sum_field) or 0.0
            results.append({"label": label, "value": total, "domain": [(groupby_field, "=", value)]})
        return results

    def _action_window(self, res_model, domain, name):
        if not res_model:
            return None
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "views": [[False, "list"], [False, "form"]],
            "target": "current",
            "domain": domain or [],
            "context": {"create": False, "edit": False},
        }

    def _chart_bar(self, title, series, color):
        labels = [entry.get("label") for entry in series]
        values = [entry.get("value") for entry in series]
        return {
            "title": title,
            "type": "bar",
            "labels": labels,
            "series": [
                {
                    "label": title,
                    "data": values,
                    "domain": series,
                }
            ],
            "color": color,
        }

    def _chart_line(self, title, series, color):
        labels = [entry.get("label") for entry in series]
        values = [entry.get("value") for entry in series]
        return {
            "title": title,
            "type": "line",
            "labels": labels,
            "series": [
                {
                    "label": title,
                    "data": values,
                    "domain": series,
                }
            ],
            "color": color,
        }

    def _chart_doughnut(self, title, series):
        labels = [entry.get("label") for entry in series]
        values = [entry.get("value") for entry in series]
        return {
            "title": title,
            "type": "doughnut",
            "labels": labels,
            "series": [
                {
                    "label": title,
                    "data": values,
                    "domain": series,
                }
            ],
        }
