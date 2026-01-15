# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models
from odoo.osv.expression import OR
from odoo.tools.misc import format_amount, format_date


class ExecutiveDashboard(models.AbstractModel):
    _name = "qlk.executive.dashboard"
    _description = "Executive Dashboard Service"

    @api.model
    def _selection_labels(self, model_name, field_name):
        model = self.env[model_name]
        field = model._fields.get(field_name)
        if not field or not getattr(field, "selection", None):
            return {}
        selection = field.selection
        if callable(selection):
            selection = field._description_selection(self.env)
        if not selection:
            return {}
        try:
            return dict(selection)
        except TypeError:
            return {}

    @api.model
    def _combine_or(self, domains):
        result = []
        for domain in domains:
            if not domain:
                continue
            if not result:
                result = domain
            else:
                result = OR([result, domain])
        return result

    @api.model
    def _lawyer_domain(self, employee_ids, user_id, field_names, allow_all=False):
        if allow_all:
            return []
        domains = []
        if employee_ids:
            for field_name in field_names:
                domains.append([(field_name, "in", employee_ids)])
        if user_id:
            domains.append([("user_id", "=", user_id)])
        combined = self._combine_or(domains)
        return combined or [(0, "=", 1)]

    @api.model
    def _group_counts(self, model, groupby, domain=None, labels=None):
        groups = model.read_group(domain or [], [groupby], [groupby], lazy=False)
        items = []
        for group in groups:
            value = group.get(groupby)
            label = ""
            if isinstance(value, (list, tuple)):
                label = value[1] if len(value) > 1 else ""
                value = value[0] if value else False
            else:
                label = labels.get(value) if labels else value
            items.append(
                {
                    "key": value,
                    "label": label or "Unassigned",
                    "count": group.get("__count", 0),
                }
            )
        items.sort(key=lambda item: item["count"], reverse=True)
        return items

    @api.model
    def _group_time_series(self, model, date_field, domain=None, lang=None):
        group_key = f"{date_field}:month"
        groups = model.read_group(domain or [], [date_field], [group_key], lazy=False)
        series = []
        for group in groups:
            raw = group.get(group_key) or group.get(date_field)
            date_value = None
            if raw:
                if isinstance(raw, (fields.Date, fields.Datetime)):
                    date_value = fields.Date.to_date(raw)
                elif isinstance(raw, str) and len(raw) >= 10 and "-" in raw:
                    date_value = fields.Date.to_date(raw)
            if not date_value:
                for entry in group.get("__domain", []):
                    if entry[0] == date_field and entry[1] == ">=":
                        date_value = fields.Date.to_date(entry[2])
                        break
            if not date_value:
                continue
            series.append((date_value, group.get("__count", 0)))
        series.sort(key=lambda item: item[0])
        labels = [format_date(self.env, item[0], lang_code=lang) for item in series]
        values = [item[1] for item in series]
        return labels, values

    @api.model
    def _lawyer_domain_for_model(self, model, allow_all, employee_ids, user_id, field_names):
        available = [name for name in field_names if name in model._fields]
        if "lawyer_id" in model._fields and "lawyer_id" not in available:
            available.insert(0, "lawyer_id")
        return self._lawyer_domain(employee_ids, user_id, available, allow_all)

    @api.model
    def _badge_color(self, category, key):
        palette = {
            "case_state": {
                "study": "#2D9CDB",
                "prosecution": "#27AE60",
                "judge": "#1F6FEB",
                "execution": "#F4B740",
                "termination": "#E86A50",
                "stop": "#8E7CC3",
                "save": "#95A5A6",
            },
            "hearing_state": {
                "new": "#F4B740",
                "process": "#2D9CDB",
                "finish": "#27AE60",
                "confirmed": "#1F6FEB",
                "cancelled": "#E86A50",
            },
            "memo_state": {
                "new": "#F4B740",
                "process": "#2D9CDB",
                "finish": "#27AE60",
                "confirmed": "#1F6FEB",
                "cancelled": "#E86A50",
            },
        }
        return palette.get(category, {}).get(key, "#94A3B8")

    @api.model
    def _count_records(self, model, domain):
        groups = model.read_group(domain or [], ["id"], [], lazy=False)
        if not groups:
            return 0
        return groups[0].get("__count", 0)

    @api.model
    def _get_actions(self):
        refs = {
            "cases": "qlk_law.act_open_qlk_case_view",
            "hearings": "qlk_law.act_open_qlk_hearing_view",
            "memos": "qlk_law.act_open_qlk_memo_view",
            "approvals": "qlk_approval.action_approval_request",
            "cases_by_court_bar": "qlk_executive_dashboard.action_exec_cases_by_court_bar",
            "sessions_by_status": "qlk_executive_dashboard.action_exec_sessions_by_status",
            "memos_by_stage": "qlk_executive_dashboard.action_exec_memos_by_stage",
            "cases_trend": "qlk_executive_dashboard.action_exec_cases_trend",
            "sessions_timeline": "qlk_executive_dashboard.action_exec_sessions_timeline",
            "cases_by_court_pie": "qlk_executive_dashboard.action_exec_cases_by_court_pie",
            "memos_by_type": "qlk_executive_dashboard.action_exec_memos_by_type",
            "lawyer_workload": "qlk_executive_dashboard.action_exec_lawyer_workload",
            "case_status_flow": "qlk_executive_dashboard.action_exec_case_status_flow",
            "session_outcomes": "qlk_executive_dashboard.action_exec_session_outcomes",
            "memo_lifecycle": "qlk_executive_dashboard.action_exec_memo_lifecycle",
        }
        data = {}
        for key, xml_id in refs.items():
            action = self.env.ref(xml_id, raise_if_not_found=False)
            if action:
                data[key] = action.id
        return data

    @api.model
    def _action_dict(self, name, res_model, domain=None):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "views": [[False, "list"], [False, "form"]],
            "target": "current",
            "domain": domain or [],
        }

    @api.model
    def _color_scale(self):
        return [
            "#1F6FEB",
            "#13B5B1",
            "#F4B740",
            "#E86A50",
            "#8E7CC3",
            "#2D9CDB",
            "#27AE60",
            "#EB5757",
        ]

    @api.model
    def _card_colors(self):
        return {
            "cases": "#1F6FEB",
            "hearings": "#13B5B1",
            "memos": "#8E7CC3",
            "approvals": "#27AE60",
        }

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        lang = user.lang or "en_US"
        employee_ids = user.employee_ids.ids
        today = fields.Date.context_today(self)

        allow_all = bool(
            user.has_group("qlk_executive_dashboard.group_qlk_exec")
            or user.has_group("qlk_executive_dashboard.group_qlk_manager")
            or user.has_group("qlk_executive_dashboard.group_qlk_assistant_manager")
            or user.has_group("qlk_law.group_qlk_law_manager")
            or user.has_group("base.group_system")
        )

        actions = self._get_actions()
        palette = {
            "primary": "#1F6FEB",
            "accent": "#27AE60",
            "muted": "#667085",
            "warning": "#F4B740",
            "info": "#2D9CDB",
            "danger": "#E86A50",
            "bg": "#F6F8FB",
            "card": "#FFFFFF",
            "text": "#1F2933",
            "border": "#E6EAF0",
            "shadow": "rgba(31, 41, 51, 0.08)",
        }

        case_model = "qlk.case" in self.env and self.env["qlk.case"] or False
        hearing_model = "qlk.hearing" in self.env and self.env["qlk.hearing"] or False
        memo_model = "qlk.memo" in self.env and self.env["qlk.memo"] or False
        approval_model = "approval.request" in self.env and self.env["approval.request"] or False

        case_domain = case_model and self._lawyer_domain_for_model(
            case_model,
            allow_all,
            employee_ids,
            user.id,
            ["employee_id", "employee_ids"],
        ) or []
        hearing_domain = hearing_model and self._lawyer_domain_for_model(
            hearing_model,
            allow_all,
            employee_ids,
            user.id,
            ["employee_id", "employee2_id", "employee_ids"],
        ) or []
        memo_domain = memo_model and self._lawyer_domain_for_model(
            memo_model,
            allow_all,
            employee_ids,
            user.id,
            ["employee_id"],
        ) or []
        if memo_domain is not None:
            memo_domain = (memo_domain or []) + [("is_memo", "=", True)]

        approval_domain = []
        if approval_model and not allow_all:
            approval_domain = [("line_ids.user_id", "=", user.id)]

        list_actions = {
            "cases": self._action_dict("Cases", "qlk.case", case_domain) if case_model else False,
            "hearings": self._action_dict("Sessions", "qlk.hearing", hearing_domain)
            if hearing_model
            else False,
            "memos": self._action_dict("Memos", "qlk.memo", memo_domain) if memo_model else False,
            "approvals": self._action_dict("Approvals", "approval.request", approval_domain)
            if approval_model
            else False,
        }

        totals = {
            "cases": self._count_records(case_model, case_domain) if case_model else 0,
            "sessions": self._count_records(hearing_model, hearing_domain) if hearing_model else 0,
            "memos": self._count_records(memo_model, memo_domain) if memo_model else 0,
            "approvals": self._count_records(approval_model, approval_domain) if approval_model else 0,
        }

        active_cases_domain = case_domain + [("state", "not in", ["termination", "stop", "save"])]
        active_cases = self._count_records(case_model, active_cases_domain) if case_model else 0
        sessions_today = self._count_records(
            hearing_model, hearing_domain + [("date", "=", today)]
        ) if hearing_model else 0
        pending_memos = self._count_records(
            memo_model, memo_domain + [("state", "in", ["new", "process"])]
        ) if memo_model else 0
        pending_approvals = self._count_records(
            approval_model, approval_domain + [("state", "in", ["draft", "in_progress"])]
        ) if approval_model else 0

        kpis = [
            {
                "key": "total_cases",
                "label": "Total Cases",
                "value": totals["cases"],
                "icon": "fa-briefcase",
                "color": palette["info"],
                "tag": "All cases",
                "domain": case_domain,
                "action": list_actions["cases"],
            },
            {
                "key": "active_cases",
                "label": "Active Cases",
                "value": active_cases,
                "icon": "fa-check-circle",
                "color": palette["accent"],
                "tag": "In progress",
                "domain": active_cases_domain,
                "action": list_actions["cases"],
            },
            {
                "key": "sessions_today",
                "label": "Sessions Today",
                "value": sessions_today,
                "icon": "fa-gavel",
                "color": palette["warning"],
                "tag": "Today",
                "domain": hearing_domain + [("date", "=", today)],
                "action": list_actions["hearings"],
            },
            {
                "key": "pending_memos",
                "label": "Pending Memos",
                "value": pending_memos,
                "icon": "fa-file-alt",
                "color": "#8E7CC3",
                "tag": "Requires action",
                "domain": memo_domain + [("state", "in", ["new", "process"])],
                "action": list_actions["memos"],
            },
            {
                "key": "pending_approvals",
                "label": "Pending Approvals",
                "value": pending_approvals,
                "icon": "fa-hourglass-half",
                "color": "#E67E22",
                "tag": "Waiting decision",
                "domain": approval_domain + [("state", "in", ["draft", "in_progress"])],
                "action": list_actions["approvals"],
            },
        ]

        charts = {}
        colors = self._color_scale()

        if case_model:
            case_labels = self._selection_labels("qlk.case", "state")
            case_stage_groups = self._group_counts(case_model, "state", case_domain, case_labels)
            charts["cases_by_stage"] = {
                "title": "Cases by Stage",
                "subtitle": "Distribution across procedures",
                "type": "bar",
                "labels": [item["label"] for item in case_stage_groups],
                "datasets": [
                    {
                        "label": "Cases",
                        "data": [item["count"] for item in case_stage_groups],
                        "backgroundColor": [
                            colors[idx % len(colors)] for idx in range(len(case_stage_groups))
                        ],
                    }
                ],
                "action": actions.get("cases"),
            }

            court_labels = self._selection_labels("qlk.casegroup", "court")
            court_groups = case_model.read_group(
                case_domain,
                ["case_group", "case_group.court"],
                ["case_group"],
                lazy=False,
            )
            court_map = defaultdict(int)
            for group in court_groups:
                court_key = group.get("case_group.court")
                if not court_key:
                    continue
                court_map[court_key] += group.get("__count", 0)
            court_items = sorted(court_map.items(), key=lambda item: item[1], reverse=True)
            chart_colors = [colors[idx % len(colors)] for idx in range(len(court_items))]
            charts["courts_distribution"] = {
                "title": "Courts Distribution",
                "subtitle": "Primary, appeal, cassation, execution",
                "type": "doughnut",
                "labels": [court_labels.get(key, key) for key, _ in court_items],
                "datasets": [
                    {
                        "label": "Cases",
                        "data": [value for _, value in court_items],
                        "backgroundColor": chart_colors,
                    }
                ],
                "action": actions.get("cases_by_court_pie"),
            }

            case_trend_labels, case_trend_values = self._group_time_series(
                case_model, "date", case_domain, lang
            )
            charts["cases_trend"] = {
                "title": "Case Creation Trend",
                "subtitle": "Monthly case intake",
                "type": "line",
                "labels": case_trend_labels,
                "datasets": [
                    {
                        "label": "Cases",
                        "data": case_trend_values,
                        "borderColor": colors[0],
                        "backgroundColor": "rgba(31, 111, 235, 0.15)",
                        "fill": True,
                    }
                ],
                "action": actions.get("cases_trend"),
            }

            workload = case_model.read_group(
                case_domain,
                ["employee_id", "state"],
                ["employee_id", "state"],
                lazy=False,
            )
            workload_map = defaultdict(lambda: defaultdict(int))
            employee_labels = {}
            state_labels = self._selection_labels("qlk.case", "state")
            for group in workload:
                employee = group.get("employee_id")
                state_key = group.get("state")
                if employee:
                    employee_labels[employee[0]] = employee[1]
                    workload_map[employee[0]][state_key] += group.get("__count", 0)
            employee_ids_sorted = sorted(employee_labels.keys(), key=lambda key: employee_labels[key])
            state_keys = list(state_labels.keys())
            datasets = []
            for index, state_key in enumerate(state_keys):
                datasets.append(
                    {
                        "label": state_labels.get(state_key, state_key),
                        "data": [workload_map[emp_id].get(state_key, 0) for emp_id in employee_ids_sorted],
                        "backgroundColor": colors[index % len(colors)],
                    }
                )
            charts["lawyer_workload"] = {
                "title": "Lawyer Workload",
                "subtitle": "Cases per lawyer by stage",
                "type": "bar",
                "stacked": True,
                "labels": [employee_labels[emp_id] for emp_id in employee_ids_sorted],
                "datasets": datasets,
                "action": actions.get("lawyer_workload"),
            }

        if hearing_model:
            hearing_labels = self._selection_labels("qlk.hearing", "state")
            hearing_groups = self._group_counts(hearing_model, "state", hearing_domain, hearing_labels)
            charts["sessions_by_status"] = {
                "title": "Sessions by Status",
                "subtitle": "Session pipeline",
                "type": "bar",
                "labels": [item["label"] for item in hearing_groups],
                "datasets": [
                    {
                        "label": "Sessions",
                        "data": [item["count"] for item in hearing_groups],
                        "backgroundColor": [
                            colors[idx % len(colors)] for idx in range(len(hearing_groups))
                        ],
                    }
                ],
                "action": actions.get("sessions_by_status"),
            }

        if memo_model:
            memo_type_groups = memo_model.read_group(
                memo_domain, ["category_id"], ["category_id"], lazy=False
            )
            memo_type_items = []
            for group in memo_type_groups:
                value = group.get("category_id")
                label = value[1] if value else "Unassigned"
                memo_type_items.append(
                    {
                        "label": label,
                        "count": group.get("__count", 0),
                    }
                )
            memo_type_items.sort(key=lambda item: item["count"], reverse=True)
            charts["memos_by_type"] = {
                "title": "Memos per Type",
                "subtitle": "Category distribution",
                "type": "pie",
                "labels": [item["label"] for item in memo_type_items],
                "datasets": [
                    {
                        "label": "Memos",
                        "data": [item["count"] for item in memo_type_items],
                        "backgroundColor": [
                            colors[idx % len(colors)] for idx in range(len(memo_type_items))
                        ],
                    }
                ],
                "action": actions.get("memos_by_type"),
            }

        avg_cycle_days = 0.0
        if case_model:
            cycle_cases = case_model.search(
                case_domain + [("date", "!=", False), ("last_hearing_date", "!=", False)],
                limit=200,
            )
            total_days = 0
            for record in cycle_cases:
                start = fields.Date.to_date(record.date)
                end = fields.Date.to_date(record.last_hearing_date)
                if start and end and end >= start:
                    total_days += (end - start).days
            if cycle_cases:
                avg_cycle_days = round(total_days / len(cycle_cases), 1)

        closed_sessions = self._count_records(
            hearing_model, hearing_domain + [("state", "=", "finish")]
        ) if hearing_model else 0
        overdue_items = self._count_records(
            hearing_model,
            hearing_domain + [("date", "<", today), ("state", "not in", ["finish", "cancelled"])],
        ) if hearing_model else 0
        closed_cases = self._count_records(
            case_model, case_domain + [("state", "=", "termination")]
        ) if case_model else 0
        performance_rate = round((closed_cases / totals["cases"]) * 100, 1) if totals["cases"] else 0

        side_metrics = [
            {
                "label": "Average Cycle Time",
                "value": f"{avg_cycle_days} days" if avg_cycle_days else "-",
                "icon": "fa-clock",
            },
            {
                "label": "Sessions Closed",
                "value": closed_sessions,
                "icon": "fa-check-circle",
            },
            {
                "label": "Overdue Items",
                "value": overdue_items,
                "icon": "fa-exclamation-circle",
            },
            {
                "label": "Performance",
                "value": f"{performance_rate}%",
                "icon": "fa-chart-line",
            },
        ]

        tables = {
            "cases": {
                "title": "My Cases",
                "rows": [],
                "action": list_actions["cases"],
            },
            "sessions": {
                "title": "My Sessions",
                "rows": [],
                "action": list_actions["hearings"],
            },
            "memos": {
                "title": "My Memos",
                "rows": [],
                "action": list_actions["memos"],
            },
        }

        if case_model:
            state_labels = self._selection_labels("qlk.case", "state")
            status_labels = self._selection_labels("qlk.case", "status")
            for record in case_model.search(case_domain, order="write_date desc", limit=7):
                amount = record.case_value or 0.0
                meta = (
                    format_amount(self.env, amount, currency=record.currency_id)
                    if amount
                    else status_labels.get(record.status, record.status)
                )
                tables["cases"]["rows"].append(
                    {
                        "id": record.id,
                        "reference": record.name or "",
                        "client": record.client_id.name or "",
                        "meta": meta or "",
                        "stage": state_labels.get(record.state, record.state),
                        "badge_color": self._badge_color("case_state", record.state),
                        "url": {"res_model": "qlk.case", "res_id": record.id},
                    }
                )

        if hearing_model:
            hearing_labels = self._selection_labels("qlk.hearing", "state")
            for record in hearing_model.search(hearing_domain, order="date desc", limit=7):
                tables["sessions"]["rows"].append(
                    {
                        "id": record.id,
                        "reference": record.name or "",
                        "client": record.case_id.client_id.name if record.case_id else "",
                        "meta": record.date and format_date(self.env, record.date, lang_code=lang) or "",
                        "stage": hearing_labels.get(record.state, record.state),
                        "badge_color": self._badge_color("hearing_state", record.state),
                        "url": {"res_model": "qlk.hearing", "res_id": record.id},
                    }
                )

        if memo_model:
            memo_labels = self._selection_labels("qlk.memo", "state")
            for record in memo_model.search(memo_domain, order="date desc", limit=7):
                tables["memos"]["rows"].append(
                    {
                        "id": record.id,
                        "reference": record.name or "",
                        "client": record.case_id.name if record.case_id else "",
                        "meta": record.date and format_date(self.env, record.date, lang_code=lang) or "",
                        "stage": memo_labels.get(record.state, record.state),
                        "badge_color": self._badge_color("memo_state", record.state),
                        "url": {"res_model": "qlk.memo", "res_id": record.id},
                    }
                )

        return {
            "user": {
                "name": user.name,
                "company": user.company_id.display_name if user.company_id else "",
            },
            "palette": palette,
            "totals": totals,
            "kpis": kpis,
            "charts": charts,
            "side_metrics": side_metrics,
            "tables": tables,
        }
