# -*- coding: utf-8 -*-
from collections import OrderedDict

from odoo import _, api, fields, models
from odoo.osv.expression import AND, OR
from odoo.tools.misc import format_date


class DynamicAnalysisDashboard(models.AbstractModel):
    _name = "qlk.dynamic.analysis.dashboard"
    _description = "Dynamic Analytical Dashboard Service"

    def _format_number(self, value, precision=0):
        if value is None:
            return "0"
        if isinstance(value, (int, float)):
            if precision:
                return f"{value:.{precision}f}"
            return f"{int(round(value))}"
        return str(value)

    def _series_values(self, series):
        return [
            float(entry.get("value", 0.0) or 0.0)
            for entry in (series or [])
            if isinstance(entry, dict)
        ]

    def _latest_pair(self, series):
        values = self._series_values(series)
        if not values:
            return 0.0, 0.0
        last = values[-1]
        previous = values[-2] if len(values) > 1 else 0.0
        return last, previous

    def _percent_delta(self, series):
        last, previous = self._latest_pair(series)
        if last == previous:
            return "0%", "steady"
        if previous == 0:
            if last == 0:
                return "0%", "steady"
            return "+100%", "up"
        change = ((last - previous) / previous) * 100.0
        if abs(change) < 0.05:
            return "0%", "steady"
        trend = "up" if change > 0 else "down"
        return f"{change:+.1f}%", trend

    def _absolute_delta(self, series, precision=1, suffix=""):
        last, previous = self._latest_pair(series)
        diff = last - previous
        threshold = 0.5 if precision == 0 else 10 ** -(precision + 1)
        if abs(diff) <= threshold:
            return "0", "steady"
        trend = "up" if diff > 0 else "down"
        if precision:
            delta = f"{diff:+.{precision}f}{suffix}"
        else:
            delta = f"{diff:+.0f}{suffix}"
        return delta, trend

    def _format_month_label(self, label):
        if not label:
            return ""
        try:
            date_value = fields.Date.to_date(f"{label}-01")
        except ValueError:
            return label
        lang = self.env.user.lang or "en_US"
        return format_date(self.env, date_value, lang_code=lang, date_format="MMM yyyy")

    def _chart_coordinates(self, series):
        labels = []
        values = []
        for entry in series or []:
            label = entry.get("label")
            labels.append(self._format_month_label(label))
            values.append(entry.get("value", 0))
        return labels, values

    def _combine_monthly_series(self, mapping):
        """Align multiple monthly series on the same label axis."""
        if not mapping:
            return [], []

        ordered_labels = OrderedDict()
        for entries in mapping.values():
            for entry in entries or []:
                label = entry.get("label")
                if not label:
                    continue
                ordered_labels.setdefault(label, 0)

        if not ordered_labels:
            return [], []

        raw_labels = list(ordered_labels.keys())
        formatted_labels = [self._format_month_label(label) for label in raw_labels]

        datasets = []
        for serie_label, entries in mapping.items():
            buckets = {entry.get("label"): entry.get("value", 0) for entry in entries or []}
            datasets.append(
                {
                    "label": serie_label,
                    "data": [buckets.get(label, 0) for label in raw_labels],
                }
            )
        return formatted_labels, datasets

    def _build_cards(self, analysis):
        totals = analysis.get("totals", {})
        series = analysis.get("series", {})

        cards = []

        def _add_card(title, total_key, series_key, subtitle):
            delta, trend = self._percent_delta(series.get(series_key))
            cards.append(
                {
                    "title": title,
                    "value": self._format_number(totals.get(total_key, 0)),
                    "delta": delta,
                    "trend": trend,
                    "subtitle": subtitle,
                }
            )

        _add_card(_("Matters in scope"), "cases", "cases", _("vs previous month"))
        _add_card(_("Hearings scheduled"), "hearings", "hearings", _("calendar comparison"))

        if series.get("consultations") or totals.get("consultations"):
            _add_card(
                _("Consultations logged"),
                "consultations",
                "consultations",
                _("client advisory trend"),
            )

        if series.get("complaints") or totals.get("complaints"):
            _add_card(
                _("Reports / Notices"),
                "complaints",
                "complaints",
                _("regulatory submissions"),
            )

        projects_series = series.get("projects")
        if projects_series:
            _add_card(
                _("Active projects"),
                "projects",
                "projects",
                _("pipeline month-over-month"),
            )

        return cards

    def _build_charts(self, analysis, palette, case_tracks=None):
        charts = {}
        series = analysis.get("series", {})

        activity_sources = OrderedDict()
        for key, label in [
            ("cases", _("Cases")),
            ("hearings", _("Hearings")),
            ("consultations", _("Consultations")),
            ("complaints", _("Reports / Notices")),
            ("projects", _("Projects")),
        ]:
            data = series.get(key)
            if data:
                activity_sources[label] = data

        activity_labels, activity_datasets = self._combine_monthly_series(activity_sources)
        if activity_labels and activity_datasets:
            charts["activity_mix"] = {
                "title": _("Integrated activity mix"),
                "type": "line",
                "labels": activity_labels,
                "series": activity_datasets,
                "color": [
                    palette.get("primary"),
                    palette.get("accent"),
                    palette.get("warning"),
                    palette.get("success"),
                    palette.get("muted"),
                ],
            }

        department_series = series.get("task_department", [])
        if department_series:
            dept_labels = [entry.get("label") for entry in department_series]
            dept_values = [entry.get("value", 0) for entry in department_series]
            charts["department_load"] = {
                "title": _("Workload by department"),
                "type": "bar",
                "labels": dept_labels,
                "series": [
                    {
                        "label": _("Open tasks"),
                        "data": dept_values,
                    }
                ],
                "color": palette.get("accent"),
            }

        status_series = series.get("case_status", [])
        if status_series:
            status_labels = [entry.get("label") for entry in status_series]
            status_values = [entry.get("value", 0) for entry in status_series]
            charts["case_status_mix"] = {
                "title": _("Case status mix"),
                "type": "doughnut",
                "labels": status_labels,
                "series": [
                    {
                        "label": _("Cases"),
                        "data": status_values,
                    }
                ],
                "color": [
                    palette.get("primary"),
                    palette.get("accent"),
                    palette.get("success"),
                    palette.get("danger"),
                    palette.get("muted"),
                ],
            }

        case_track_series = case_tracks or []
        if case_track_series:
            charts["case_track_mix"] = {
                "title": _("Case track coverage"),
                "type": "doughnut",
                "labels": [entry.get("label") for entry in case_track_series],
                "series": [
                    {
                        "label": _("Cases"),
                        "data": [entry.get("value", 0) for entry in case_track_series],
                    }
                ],
                "color": [
                    palette.get("primary"),
                    palette.get("accent"),
                    palette.get("success"),
                    palette.get("warning"),
                    palette.get("danger"),
                ],
            }

        hours_series = series.get("task_hours", [])
        labels_hours, hours_values = self._chart_coordinates(hours_series)
        if labels_hours:
            charts["hours_trend"] = {
                "title": _("Approved hours trend"),
                "type": "bar",
                "labels": labels_hours,
                "series": [
                    {
                        "label": _("Hours"),
                        "data": hours_values,
                    }
                ],
                "color": palette.get("success"),
            }

        return charts

    def _task_scope_domain(self, allow_all, employee_ids, user):
        domain = [("project_id", "!=", False)]
        if allow_all:
            return domain
        if employee_ids:
            domain.append(("employee_id", "in", employee_ids))
        else:
            domain.append(("assigned_user_id", "=", user.id))
        return domain

    def _case_track_field(self):
        if "qlk.case" not in self.env:
            return None
        Case = self.env["qlk.case"]
        candidates = [
            "case_track",
            "practice_track",
            "business_track",
            "service_line",
            "litigation_track",
        ]
        for field_name in candidates:
            if field_name in Case._fields:
                return field_name
        return None

    def _case_tracks_data(self):
        if "qlk.case" not in self.env:
            return []
        Case = self.env["qlk.case"]
        field_name = self._case_track_field()
        if not field_name:
            return []

        field = Case._fields[field_name]
        grouped = Case.read_group([], [field_name], [field_name])
        results = []
        selection = {}
        if field.type == "selection":
            selection = dict(field.selection)

        for entry in grouped:
            raw_value = entry.get(field_name)
            count = entry.get(f"{field_name}_count", 0)
            if not raw_value:
                continue
            if field.type == "selection":
                label = selection.get(raw_value, raw_value)
            elif field.type == "many2one":
                if isinstance(raw_value, tuple):
                    label = raw_value[1]
                else:
                    label = self.env[field.comodel_name].browse(raw_value).display_name
            else:
                label = raw_value
            results.append({"label": label, "value": count})
        return results

    def _build_hours_tasks(self, analysis):
        series = analysis.get("series", {})
        totals = analysis.get("totals", {})
        hours_suffix = _("h")

        hours_value = totals.get("task_hours", 0.0) or 0.0
        formatted_hours = f"{self._format_number(hours_value, precision=1)}{hours_suffix}"
        delta, trend = self._absolute_delta(
            series.get("task_hours"), precision=1, suffix=hours_suffix
        )

        labels, values = self._chart_coordinates(series.get("task_hours"))

        user = self.env.user
        allow_all = True
        employee_ids = user.employee_ids.ids
        status_counts = {"approved": 0, "waiting": 0, "draft": 0, "rejected": 0}
        total_tasks = 0

        if "qlk.task" in self.env:
            Task = self.env["qlk.task"]
            domain = self._task_scope_domain(allow_all, employee_ids, user)
            grouped = Task.read_group(domain, ["approval_state"], ["approval_state"])
            for entry in grouped:
                state = entry.get("approval_state")
                count = entry.get("approval_state_count", 0)
                total_tasks += count
                if state in status_counts:
                    status_counts[state] = count

        department_breakdown = [
            {
                "label": entry.get("label"),
                "value": entry.get("value", 0),
            }
            for entry in series.get("task_department", []) or []
        ]

        return {
            "total_hours": formatted_hours,
            "delta": delta,
            "trend": trend,
            "series": {
                "labels": labels,
                "values": values,
            },
            "status": status_counts,
            "total_tasks": total_tasks,
            "department_breakdown": department_breakdown,
        }

    def _combine_or(self, domains):
        result = []
        for domain in domains:
            if not domain:
                continue
            result = domain if not result else OR([result, domain])
        return result

    def _selection_label(self, record, field_name):
        field = record._fields.get(field_name)
        if field and getattr(field, "selection", None):
            return dict(field.selection).get(record[field_name], record[field_name])
        return record[field_name]

    def _build_timeline(self):
        events = []
        today = fields.Date.context_today(self)
        user = self.env.user
        employee_ids = user.employee_ids.ids
        is_manager = True
        lang = user.lang or "en_US"

        if "qlk.hearing" in self.env:
            Hearing = self.env["qlk.hearing"]
            domain_parts = []
            if not is_manager:
                employee_domains = []
                for field_name in ("employee_id", "employee2_id", "employee_ids"):
                    if field_name in Hearing._fields and employee_ids:
                        employee_domains.append([(field_name, "in", employee_ids)])
                employee_domain = self._combine_or(employee_domains)
                if employee_domain:
                    domain_parts.append(employee_domain)
            domain_parts.append([("date", ">=", today)])
            hearing_domain = domain_parts[0] if len(domain_parts) == 1 else AND(domain_parts)
            hearings = Hearing.search(hearing_domain, order="date asc", limit=4)
            for hearing in hearings:
                status = self._selection_label(hearing, "state") or ""
                timeline_state = self._timeline_state(hearing.state, today == hearing.date)
                events.append(
                    {
                        "period": format_date(self.env, hearing.date, lang_code=lang),
                        "title": hearing.case_id.name or hearing.name,
                        "status": timeline_state,
                        "description": status,
                    }
                )

        remaining = 4 - len(events)
        if remaining > 0 and "qlk.task" in self.env:
            Task = self.env["qlk.task"]
            task_domain = [("approval_state", "=", "waiting")]
            if not is_manager and employee_ids:
                task_domain = AND(
                    [
                        task_domain,
                        [("employee_id", "in", employee_ids)],
                    ]
                )
            tasks = Task.search(task_domain, order="date_start asc", limit=remaining)
            for task in tasks:
                date_value = task.date_start or today
                events.append(
                    {
                        "period": format_date(self.env, date_value, lang_code=lang),
                        "title": task.name,
                        "status": "ongoing",
                        "description": _("Awaiting approval · %(hours).1f h", hours=task.hours_spent),
                    }
                )

        return events

    def _timeline_state(self, raw_state, is_today=False):
        state = (raw_state or "").lower()
        if state in {"done", "closed", "finished"}:
            return "done"
        if state in {"in_progress", "progress", "confirmed", "ongoing"} or is_today:
            return "ongoing"
        if state in {"cancel", "cancelled", "draft"}:
            return "planned"
        return "planned"

    def _build_insights(self, analysis, case_tracks=None):
        insights = []
        series = analysis.get("series", {})

        case_status = series.get("case_status", [])
        if case_status:
            top_status = max(case_status, key=lambda entry: entry.get("value", 0))
            insights.append(
                {
                    "title": _("Leading case status"),
                    "body": _(
                        "%(count)s matters are currently %(status)s.",
                        count=int(top_status.get("value", 0)),
                        status=top_status.get("label"),
                    ),
                }
            )

        if case_tracks:
            top_track = max(case_tracks, key=lambda entry: entry.get("value", 0))
            if top_track and top_track.get("value"):
                insights.append(
                    {
                        "title": _("Dominant case track"),
                        "body": _(
                            "%(count)s cases belong to %(track)s engagements.",
                            count=int(top_track.get("value", 0)),
                            track=top_track.get("label"),
                        ),
                    }
                )

        task_department = series.get("task_department", [])
        if task_department:
            top_department = max(task_department, key=lambda entry: entry.get("value", 0))
            insights.append(
                {
                    "title": _("Department workload focus"),
                    "body": _(
                        "%(count)s open tasks belong to %(department)s.",
                        count=int(top_department.get("value", 0)),
                        department=top_department.get("label"),
                    ),
                }
            )

        task_hours = series.get("task_hours", [])
        last_hours, previous_hours = self._latest_pair(task_hours)
        if last_hours or previous_hours:
            hours_suffix = _("h")
            delta, trend = self._absolute_delta(task_hours, precision=1, suffix=hours_suffix)
            zero_tokens = {"0", f"0{hours_suffix}", f"+0{hours_suffix}", f"-0{hours_suffix}"}
            delta_text = delta if delta not in zero_tokens else _("no change")
            insights.append(
                {
                    "title": _("Approved hours momentum"),
                    "body": _(
                        "Last month recorded %(hours).1f h (%(delta)s vs previous).",
                        hours=last_hours,
                        delta=delta_text,
                    ),
                }
            )

        return insights

    def _fallback_payload(self):
        palette = {
            "primary": "#0F5CA8",
            "accent": "#22B6C8",
            "muted": "#1F3B57",
            "success": "#27AE60",
            "warning": "#F39C12",
            "danger": "#C0392B",
        }
        cards = [
            {
                "title": _("Matters in scope"),
                "value": "148",
                "delta": "+8%",
                "trend": "up",
                "subtitle": _("vs previous month"),
            },
            {
                "title": _("Hearings scheduled"),
                "value": "62",
                "delta": "-5%",
                "trend": "down",
                "subtitle": _("calendar comparison"),
            },
            {
                "title": _("Consultations logged"),
                "value": "37",
                "delta": "+11%",
                "trend": "up",
                "subtitle": _("client advisory trend"),
            },
            {
                "title": _("Reports / Notices"),
                "value": "21",
                "delta": "+2",
                "trend": "steady",
                "subtitle": _("regulatory submissions"),
            },
            {
                "title": _("Active projects"),
                "value": "54",
                "delta": "+6",
                "trend": "steady",
                "subtitle": _("pipeline month-over-month"),
            },
        ]
        charts = {
            "activity_mix": {
                "title": _("Integrated activity mix"),
                "type": "line",
                "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                "series": [
                    {"label": _("Cases"), "data": [35, 42, 48, 40, 52, 58]},
                    {"label": _("Hearings"), "data": [22, 28, 31, 29, 35, 32]},
                    {"label": _("Consultations"), "data": [12, 14, 18, 16, 19, 20]},
                    {"label": _("Reports / Notices"), "data": [6, 7, 9, 8, 10, 11]},
                ],
                "color": palette["primary"],
            },
            "department_load": {
                "title": _("Workload by department"),
                "type": "bar",
                "labels": [_("Litigation"), _("Corporate"), _("Pre-Litigation"), _("Management")],
                "series": [
                    {"label": _("Open tasks"), "data": [120, 98, 56, 73]},
                ],
                "color": palette["accent"],
            },
            "case_status_mix": {
                "title": _("Case status mix"),
                "type": "doughnut",
                "labels": [_("Still"), _("Success"), _("Failed")],
                "series": [
                    {"label": _("Cases"), "data": [62, 29, 9]},
                ],
                "color": [palette["success"], palette["muted"], palette["danger"]],
            },
            "case_track_mix": {
                "title": _("Case track coverage"),
                "type": "doughnut",
                "labels": [_("Litigation"), _("Corporate"), _("Pre-Litigation")],
                "series": [
                    {"label": _("Cases"), "data": [78, 34, 18]},
                ],
                "color": [palette["primary"], palette["accent"], palette["warning"]],
            },
            "hours_trend": {
                "title": _("Approved hours trend"),
                "type": "bar",
                "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                "series": [
                    {"label": _("Hours"), "data": [118, 134, 146, 152, 163, 178]},
                ],
                "color": palette["success"],
            },
        }
        timeline = [
            {
                "period": "Week 1",
                "title": "Regulatory Filing",
                "status": "done",
                "description": "Filed compliance review for corporate client Alpha LLC.",
            },
            {
                "period": "Week 2",
                "title": "Arbitration Hearing",
                "status": "ongoing",
                "description": "Preparation and attendance for arbitration case #ARB-204.",
            },
            {
                "period": "Week 3",
                "title": "M&A Due Diligence",
                "status": "planned",
                "description": "Kick-off for cross-border acquisition due diligence.",
            },
        ]
        insights = [
            {
                "title": "Peak Closure Rate",
                "body": "June recorded the highest matter closure rate with 49 resolutions completed.",
            },
            {
                "title": "Emerging Practice",
                "body": "Advisory workload increased by 15% compared to the previous period.",
            },
            {
                "title": "Client Experience",
                "body": "Promoter ratio reached 62% following the new intake workflow deployment.",
            },
        ]
        hours_tasks = {
            "total_hours": "178h",
            "delta": "+12h",
            "trend": "up",
            "series": {
                "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                "values": [118, 134, 146, 152, 163, 178],
            },
            "status": {
                "approved": 46,
                "waiting": 18,
                "draft": 6,
                "rejected": 3,
            },
            "total_tasks": 73,
            "department_breakdown": [
                {"label": _("Litigation"), "value": 32},
                {"label": _("Corporate"), "value": 21},
                {"label": _("Pre-Litigation"), "value": 14},
                {"label": _("Management"), "value": 6},
            ],
        }
        return {
            "palette": palette,
            "cards": cards,
            "charts": charts,
            "timeline": timeline,
            "insights": insights,
            "actions": {},
            "hours_tasks": hours_tasks,
        }

    @api.model
    def get_dashboard_data(self):
        if "qlk.analysis.dashboard" not in self.env:
            return self._fallback_payload()

        analysis = self.env["qlk.analysis.dashboard"].get_dashboard_data(months=6)

        palette = analysis.get("palette") or {
            "primary": "#0F5CA8",
            "accent": "#22B6C8",
            "muted": "#1F3B57",
            "success": "#27AE60",
            "warning": "#F39C12",
            "danger": "#C0392B",
        }

        cards = self._build_cards(analysis)
        case_tracks = self._case_tracks_data()
        charts = self._build_charts(analysis, palette, case_tracks=case_tracks)
        timeline = self._build_timeline()
        insights = self._build_insights(analysis, case_tracks=case_tracks)
        hours_tasks = self._build_hours_tasks(analysis)

        return {
            "palette": palette,
            "cards": cards,
            "charts": charts,
            "timeline": timeline,
            "insights": insights,
            "actions": analysis.get("actions", {}),
            "hours_tasks": hours_tasks,
        }
