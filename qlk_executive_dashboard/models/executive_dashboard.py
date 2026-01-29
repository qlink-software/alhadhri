# -*- coding: utf-8 -*-

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
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
    def _employee_domain(self, model, employee_ids, user_id=None, employee_fields=None, user_field=None, allow_all=False):
        if allow_all:
            return []
        domains = []
        employee_fields = employee_fields or []
        for field_name in employee_fields:
            if field_name in model._fields and employee_ids:
                domains.append([(field_name, "in", employee_ids)])
        if user_field and user_field in model._fields and user_id:
            domains.append([(user_field, "=", user_id)])
        combined = self._combine_or(domains)
        return combined or [(0, "=", 1)]

    @api.model
    def _team_employee_ids(self, employee_ids):
        if not employee_ids or "hr.employee" not in self.env:
            return employee_ids
        employees = self.env["hr.employee"].search([("id", "child_of", employee_ids)])
        return employees.ids

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
    def _sum_field(self, model, domain, field_name):
        grouped = model.read_group(domain or [], [field_name], [], lazy=False)
        if not grouped:
            return 0.0
        return grouped[0].get(field_name, 0.0) or 0.0

    @api.model
    def _count_records(self, model, domain):
        groups = model.read_group(domain or [], ["id"], [], lazy=False)
        if not groups:
            return 0
        return groups[0].get("__count", 0)

    @api.model
    def _action_dict(self, name, res_model, domain=None, view_modes=None):
        view_modes = view_modes or ["list", "form"]
        views = [[False, view_modes[0]]]
        for mode in view_modes[1:]:
            views.append([False, mode])
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "views": views,
            "target": "current",
            "domain": domain or [],
        }

    @api.model
    def _color_scale(self):
        return [
            "#0F5CA8",
            "#22B6C8",
            "#27AE60",
            "#F4B740",
            "#E86A50",
            "#0D3E7A",
        ]

    @api.model
    def _safe_model(self, model_name):
        return self.env[model_name] if model_name in self.env else False

    @api.model
    def _safe_read_group(self, model, domain, fields_list, groupby):
        try:
            model.check_access_rights("read")
            return model.read_group(domain, fields_list, groupby, lazy=False)
        except AccessError:
            return []

    @api.model
    def _safe_count(self, model, domain):
        try:
            model.check_access_rights("read")
            return model.search_count(domain)
        except AccessError:
            return 0

    @api.model
    def _safe_search_read(self, model, domain, fields_list, limit=None, order=None):
        try:
            model.check_access_rights("read")
            return model.search_read(domain, fields_list, limit=limit, order=order)
        except AccessError:
            return []

    @api.model
    def _format_amount(self, amount, currency):
        try:
            return format_amount(self.env, amount or 0.0, currency)
        except Exception:
            return f"{amount or 0.0:,.2f}"

    @api.model
    def _first_field(self, model, candidates):
        for field_name in candidates:
            if field_name in model._fields:
                return field_name
        return False

    @api.model
    def _format_date_value(self, value, lang):
        if not value:
            return ""
        if isinstance(value, str):
            parsed = fields.Date.to_date(value)
        else:
            parsed = fields.Date.to_date(value) if not isinstance(value, fields.Date.__class__) else value
        if not parsed:
            try:
                parsed = fields.Datetime.to_datetime(value).date()
            except Exception:
                parsed = False
        if not parsed:
            return ""
        return format_date(self.env, parsed, lang_code=lang)

    @api.model
    def _approval_item(self, model, record, config, today, stage_labels=None):
        reference_field = config.get("reference_field")
        client_field = config.get("client_field")
        amount_field = config.get("amount_field")
        stage_field = config.get("stage_field")
        currency_field = config.get("currency_field")

        reference = record.get(reference_field) if reference_field else record.get("name")
        client_value = record.get(client_field) if client_field else False
        if isinstance(client_value, (list, tuple)):
            client_value = client_value[1] if len(client_value) > 1 else ""
        amount_value = record.get(amount_field) or 0.0
        currency_value = record.get(currency_field)
        currency = self.env["res.currency"].browse(currency_value[0]) if currency_value else self.env.company.currency_id

        stage_value = record.get(stage_field) if stage_field else False
        stage_label = ""
        if isinstance(stage_value, (list, tuple)):
            stage_label = stage_value[1] if len(stage_value) > 1 else ""
        else:
            stage_label = stage_labels.get(stage_value, stage_value) if stage_labels else stage_value

        waiting_source = record.get("write_date") or record.get("create_date")
        waiting_date = fields.Datetime.to_datetime(waiting_source) if waiting_source else None
        waiting_days = 0
        if waiting_date:
            waiting_days = max((today - waiting_date.date()).days, 0)

        return {
            "id": record["id"],
            "model": config.get("model"),
            "doc_type": config.get("doc_type"),
            "reference": reference or "",
            "client": client_value or "",
            "amount": amount_value,
            "amount_display": self._format_amount(amount_value, currency),
            "stage": stage_label or "Unassigned",
            "waiting_days": waiting_days,
        }

    @api.model
    def _build_pipeline_cards(self, model, groupby, domain, action, colors):
        labels = self._selection_labels(model._name, groupby) if groupby in model._fields else {}
        groups = self._group_counts(model, groupby, domain, labels)
        cards = []
        for index, group in enumerate(groups):
            cards.append(
                {
                    "key": f"{groupby}_{group['key']}",
                    "label": group["label"],
                    "count": group["count"],
                    "color": colors[index % len(colors)],
                    "domain": domain + [(groupby, "=", group["key"])],
                }
            )
        return {
            "cards": cards,
            "action": action,
        }

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        lang = user.lang or "en_US"
        today = fields.Date.context_today(self)
        is_manager = user.has_group("qlk_executive_dashboard.group_qlk_executive_manager")
        is_assistant = user.has_group("qlk_executive_dashboard.group_qlk_executive_assistant")
        if not (is_manager or is_assistant):
            raise AccessError("You do not have access to the executive dashboard.")

        palette = {
            "primary": "#0F5CA8",
            "accent": "#22B6C8",
            "muted": "#0D3E7A",
            "success": "#27AE60",
            "warning": "#F4B740",
            "danger": "#E86A50",
            "bg": "#F5F8FC",
            "card": "#FFFFFF",
            "text": "#1F2937",
            "border": "#E2E8F0",
            "shadow": "rgba(15, 92, 168, 0.12)",
        }

        colors = self._color_scale()
        month_start = today.replace(day=1)
        next_month = month_start + relativedelta(months=1)

        proposal_model = self._safe_model("bd.proposal")
        engagement_model = self._safe_model("bd.engagement.letter")
        project_model = self._safe_model("qlk.project") or self._safe_model("project.project")
        case_model = self._safe_model("qlk.case")
        hearing_model = self._safe_model("qlk.hearing")
        leave_model = self._safe_model("hr.leave")
        request_model = self._safe_model("qlk.request")
        approval_model = self._safe_model("approval.request")
        account_move = self._safe_model("account.move")

        approval_sources = []
        if proposal_model:
            approval_sources.append(
                {
                    "model": "bd.proposal",
                    "doc_type": "Quotation",
                    "reference_candidates": ["code", "name"],
                    "client_candidates": ["client_id", "partner_id"],
                    "amount_candidates": ["total_amount", "legal_fees"],
                    "stage_field": "state",
                    "role_field": "approval_role",
                    "currency_field": "currency_id",
                }
            )
        if engagement_model:
            approval_sources.append(
                {
                    "model": "bd.engagement.letter",
                    "doc_type": "Agreement",
                    "reference_candidates": ["code", "name"],
                    "client_candidates": ["client_id", "partner_id"],
                    "amount_candidates": ["total_amount", "legal_fee_amount"],
                    "stage_field": "state",
                    "role_field": "approval_role",
                    "currency_field": "currency_id",
                }
            )
        if project_model and "state" in project_model._fields:
            approval_sources.append(
                {
                    "model": project_model._name,
                    "doc_type": "Project",
                    "reference_candidates": ["code", "name"],
                    "client_candidates": ["client_id", "partner_id"],
                    "amount_candidates": ["total_estimated_cost", "legal_fee_amount", "amount_total"],
                    "stage_field": "stage_id" if "stage_id" in project_model._fields else "state",
                    "role_field": "approval_role" if "approval_role" in project_model._fields else False,
                    "currency_field": "currency_id" if "currency_id" in project_model._fields else False,
                }
            )

        manager_inbox = []
        assistant_queue = []
        for source in approval_sources:
            model = self.env[source["model"]]
            role_field = source.get("role_field")
            domain = [("state", "=", "waiting_manager_approval")] if "state" in model._fields else []
            if role_field and role_field in model._fields:
                role_value = "manager" if is_manager else "assistant_manager"
                domain.append((role_field, "=", role_value))

            reference_field = next(
                (field for field in source["reference_candidates"] if field in model._fields), "name"
            )
            client_field = next(
                (field for field in source["client_candidates"] if field in model._fields), False
            )
            amount_field = next(
                (field for field in source["amount_candidates"] if field in model._fields), False
            )
            currency_field = source.get("currency_field")
            if currency_field and currency_field not in model._fields:
                currency_field = False
            stage_field = source.get("stage_field") if source.get("stage_field") in model._fields else False
            stage_labels = self._selection_labels(model._name, stage_field) if stage_field else {}

            fields_list = [reference_field, "create_date", "write_date"]
            if client_field:
                fields_list.append(client_field)
            if amount_field:
                fields_list.append(amount_field)
            if stage_field:
                fields_list.append(stage_field)
            if currency_field:
                fields_list.append(currency_field)

            data = self._safe_search_read(
                model,
                domain,
                fields_list,
                limit=50,
                order="write_date asc",
            )
            config = {
                "model": source["model"],
                "doc_type": source["doc_type"],
                "reference_field": reference_field,
                "client_field": client_field,
                "amount_field": amount_field,
                "stage_field": stage_field,
                "currency_field": currency_field,
            }
            for record in data:
                item = self._approval_item(model, record, config, today, stage_labels)
                if is_manager:
                    manager_inbox.append(item)
                else:
                    assistant_queue.append(item)

        # keep oldest-first ordering from the search query

        pipeline = {}
        if proposal_model:
            action = self._action_dict("Quotations", "bd.proposal", [])
            pipeline["quotations"] = self._build_pipeline_cards(
                proposal_model, "state", [], action, colors
            )
        if engagement_model:
            action = self._action_dict("Agreements", "bd.engagement.letter", [])
            pipeline["agreements"] = self._build_pipeline_cards(
                engagement_model, "state", [], action, colors
            )
        if project_model:
            project_domain = []
            if "active" in project_model._fields:
                project_domain.append(("active", "=", True))
            if "stage_id" in project_model._fields and project_model._fields["stage_id"].store:
                groupby = "stage_id"
            elif "project_type" in project_model._fields:
                groupby = "project_type"
            elif "department" in project_model._fields:
                groupby = "department"
            else:
                groupby = "state" if "state" in project_model._fields else False
            action = self._action_dict("Projects", project_model._name, project_domain)
            if groupby:
                pipeline["projects"] = self._build_pipeline_cards(
                    project_model, groupby, project_domain, action, colors
                )

        kpis = []
        if account_move:
            date_field = "invoice_date" if "invoice_date" in account_move._fields else "date"
            amount_field = "amount_total_signed" if "amount_total_signed" in account_move._fields else "amount_total"
            revenue_domain = [
                ("state", "=", "posted"),
                ("move_type", "in", ["out_invoice", "out_refund"]),
                (date_field, ">=", month_start),
                (date_field, "<", next_month),
            ]
            revenue = self._sum_field(account_move, revenue_domain, amount_field)
            currency = self.env.company.currency_id
            kpis.append(
                {
                    "key": "revenue",
                    "label": "Total Revenue (Month)",
                    "value": revenue,
                    "display": self._format_amount(revenue, currency),
                    "icon": "fa-line-chart",
                    "action": self._action_dict("Invoices", "account.move", revenue_domain),
                }
            )

            outstanding_domain = [
                ("state", "=", "posted"),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ]
            if "payment_state" in account_move._fields:
                outstanding_domain.append(("payment_state", "not in", ["paid", "reversed"]))
            outstanding = self._sum_field(account_move, outstanding_domain, "amount_residual")
            kpis.append(
                {
                    "key": "outstanding",
                    "label": "Outstanding Invoices",
                    "value": outstanding,
                    "display": self._format_amount(outstanding, currency),
                    "icon": "fa-file-text-o",
                    "action": self._action_dict("Outstanding Invoices", "account.move", outstanding_domain),
                }
            )

        if project_model:
            project_domain = []
            if "active" in project_model._fields:
                project_domain.append(("active", "=", True))
            active_projects = self._safe_count(project_model, project_domain)
            kpis.append(
                {
                    "key": "projects",
                    "label": "Active Projects",
                    "value": active_projects,
                    "display": f"{active_projects:,}",
                    "icon": "fa-briefcase",
                    "action": self._action_dict("Projects", project_model._name, project_domain),
                }
            )

        delayed_cases = 0
        delayed_domain = []
        if case_model and "next_hearing_date" in case_model._fields:
            delayed_domain = [("next_hearing_date", "<", today)]
            delayed_cases = self._safe_count(case_model, delayed_domain)
        kpis.append(
            {
                "key": "delayed_cases",
                "label": "Delayed Cases",
                "value": delayed_cases,
                "display": f"{delayed_cases:,}",
                "icon": "fa-exclamation-triangle",
                "action": self._action_dict("Delayed Cases", "qlk.case", delayed_domain) if case_model else None,
            }
        )

        legal_dashboard = {
            "cases_by_court": {"recordset": [], "action": None},
            "cases_by_status": {"recordset": [], "action": None},
            "upcoming_sessions": {"items": [], "action": None},
        }
        if case_model:
            court_field = "case_group" if "case_group" in case_model._fields else "case_group_id"
            court_names = [
                "Court of Cassation",
                "Court of Appeal",
                "Investment & Commercial Court",
                "Execution Court",
                "Criminal Court",
                "Family Court",
            ]
            court_counts = {name: {"count": 0, "id": False} for name in court_names}
            grouped = self._safe_read_group(case_model, [], [court_field], [court_field])
            for group in grouped:
                value = group.get(court_field)
                if isinstance(value, (list, tuple)) and len(value) > 1:
                    name = value[1]
                    if name in court_counts:
                        court_counts[name]["count"] = group.get("__count", 0)
                        court_counts[name]["id"] = value[0]

            legal_dashboard["cases_by_court"]["recordset"] = [
                {
                    "category": name,
                    "count": court_counts[name]["count"],
                    "record_id": [(court_field, "=", court_counts[name]["id"])] if court_counts[name]["id"] else [],
                }
                for name in court_names
            ]
            legal_dashboard["cases_by_court"]["action"] = self._action_dict(
                "Cases by Court", case_model._name, []
            )

            status_field = "status" if "status" in case_model._fields else "state"
            if status_field in case_model._fields:
                labels = self._selection_labels(case_model._name, status_field)
                status_groups = self._safe_read_group(case_model, [], [status_field], [status_field])
                legal_dashboard["cases_by_status"]["recordset"] = [
                    {
                        "category": labels.get(group.get(status_field), group.get(status_field)) or "Undefined",
                        "value": group.get("__count", 0),
                        "domain": [(status_field, "=", group.get(status_field))],
                    }
                    for group in status_groups
                    if group.get(status_field)
                ]
                legal_dashboard["cases_by_status"]["action"] = self._action_dict(
                    "Cases by Status", case_model._name, []
                )

        if hearing_model:
            hearing_domain = [
                ("date", ">=", today),
                ("date", "<", today + timedelta(days=7)),
            ]
            hearings = hearing_model.search(hearing_domain, order="date asc", limit=6)
            legal_dashboard["upcoming_sessions"] = {
                "items": [
                    {
                        "id": hearing.id,
                        "model": "qlk.hearing",
                        "name": hearing.name or "",
                        "case": hearing.case_id.name if hearing.case_id else "",
                        "court": hearing.case_group.name if getattr(hearing, "case_group", False) else "",
                        "date": format_date(self.env, hearing.date, lang_code=lang) if hearing.date else "",
                    }
                    for hearing in hearings
                ],
                "action": self._action_dict("Hearings", "qlk.hearing", hearing_domain)
                if hearing_model
                else None,
            }

        lists = {}
        if leave_model:
            employee_field = self._first_field(leave_model, ["employee_id"])
            type_field = self._first_field(leave_model, ["holiday_status_id", "holiday_status"])
            date_from_field = self._first_field(leave_model, ["request_date_from", "date_from", "date_start"])
            date_to_field = self._first_field(leave_model, ["request_date_to", "date_to", "date_end"])
            state_field = self._first_field(leave_model, ["state"])
            order = f"{date_from_field} asc" if date_from_field else "create_date asc"
            fields_list = [employee_field, type_field, date_from_field, date_to_field, state_field, "create_date"]
            fields_list = [field for field in fields_list if field]
            records = self._safe_search_read(leave_model, [], fields_list, limit=6, order=order)
            items = []
            for record in records:
                employee = record.get(employee_field)
                leave_type = record.get(type_field)
                from_date = record.get(date_from_field)
                to_date = record.get(date_to_field)
                items.append(
                    {
                        "id": record["id"],
                        "model": "hr.leave",
                        "employee": employee[1] if isinstance(employee, (list, tuple)) else "",
                        "leave_type": leave_type[1] if isinstance(leave_type, (list, tuple)) else "",
                        "period": " - ".join(
                            [
                                value
                                for value in [
                                    self._format_date_value(from_date, lang),
                                    self._format_date_value(to_date, lang),
                                ]
                                if value
                            ]
                        ),
                        "state": record.get(state_field, ""),
                        "requested_on": self._format_date_value(record.get("create_date"), lang),
                    }
                )
            lists["leaves"] = {
                "items": items,
                "action": self._action_dict("Leave Requests", "hr.leave", []),
            }

        def _doc_list(model, key, title):
            if not model:
                return
            reference_field = self._first_field(model, ["code", "name"])
            client_field = self._first_field(model, ["client_id", "partner_id"])
            amount_field = self._first_field(model, ["total_amount", "legal_fees", "legal_fee_amount"])
            currency_field = self._first_field(model, ["currency_id"])
            state_field = self._first_field(model, ["state"])
            date_field = self._first_field(model, ["date", "create_date"])
            order = f"{date_field} asc" if date_field else "create_date asc"
            fields_list = [reference_field, client_field, amount_field, currency_field, state_field, date_field]
            fields_list = [field for field in fields_list if field]
            records = self._safe_search_read(model, [], fields_list, limit=6, order=order)
            items = []
            for record in records:
                client = record.get(client_field)
                currency_value = record.get(currency_field)
                currency = (
                    self.env["res.currency"].browse(currency_value[0])
                    if isinstance(currency_value, (list, tuple)) and currency_value
                    else self.env.company.currency_id
                )
                amount_value = record.get(amount_field, 0.0) if amount_field else 0.0
                items.append(
                    {
                        "id": record["id"],
                        "model": model._name,
                        "reference": record.get(reference_field, ""),
                        "client": client[1] if isinstance(client, (list, tuple)) else "",
                        "amount": amount_value,
                        "amount_display": self._format_amount(amount_value, currency),
                        "state": record.get(state_field, "") if state_field else "",
                        "date": self._format_date_value(record.get(date_field), lang) if date_field else "",
                    }
                )
            lists[key] = {
                "items": items,
                "action": self._action_dict(title, model._name, []),
            }

        _doc_list(proposal_model, "proposals", "Proposals")
        _doc_list(engagement_model, "agreements", "Agreements")

        if project_model:
            ref_field = self._first_field(project_model, ["code", "name"])
            client_field = self._first_field(project_model, ["client_id", "partner_id"])
            stage_field = self._first_field(project_model, ["stage_id", "stage"])
            type_field = self._first_field(project_model, ["project_type", "department"])
            date_field = self._first_field(project_model, ["create_date"])
            fields_list = [ref_field, client_field, stage_field, type_field, date_field]
            fields_list = [field for field in fields_list if field]
            records = self._safe_search_read(project_model, [], fields_list, limit=6, order="create_date asc")
            items = []
            for record in records:
                client = record.get(client_field)
                stage = record.get(stage_field)
                items.append(
                    {
                        "id": record["id"],
                        "model": project_model._name,
                        "reference": record.get(ref_field, ""),
                        "client": client[1] if isinstance(client, (list, tuple)) else "",
                        "stage": stage[1] if isinstance(stage, (list, tuple)) else stage or "",
                        "type": record.get(type_field, "") if type_field else "",
                        "date": self._format_date_value(record.get(date_field), lang),
                    }
                )
            lists["projects"] = {
                "items": items,
                "action": self._action_dict("Projects", project_model._name, []),
            }

        if case_model:
            name_field = self._first_field(case_model, ["name"])
            court_field = self._first_field(case_model, ["case_group", "case_group_id"])
            status_field = self._first_field(case_model, ["status", "state"])
            next_field = self._first_field(case_model, ["next_hearing_date", "date"])
            date_field = self._first_field(case_model, ["create_date"])
            fields_list = [name_field, court_field, status_field, next_field, date_field]
            fields_list = [field for field in fields_list if field]
            records = self._safe_search_read(case_model, [], fields_list, limit=6, order="create_date asc")
            items = []
            for record in records:
                court = record.get(court_field)
                items.append(
                    {
                        "id": record["id"],
                        "model": "qlk.case",
                        "name": record.get(name_field, ""),
                        "court": court[1] if isinstance(court, (list, tuple)) else "",
                        "status": record.get(status_field, "") if status_field else "",
                        "next_hearing": self._format_date_value(record.get(next_field), lang) if next_field else "",
                        "date": self._format_date_value(record.get(date_field), lang),
                    }
                )
            lists["cases"] = {
                "items": items,
                "action": self._action_dict("Cases", "qlk.case", []),
            }

        if hearing_model:
            name_field = self._first_field(hearing_model, ["name"])
            case_field = self._first_field(hearing_model, ["case_id"])
            court_field = self._first_field(hearing_model, ["case_group", "case_group_id"])
            date_field = self._first_field(hearing_model, ["date", "session_date"])
            state_field = self._first_field(hearing_model, ["state"])
            fields_list = [name_field, case_field, court_field, date_field, state_field]
            fields_list = [field for field in fields_list if field]
            records = self._safe_search_read(hearing_model, [], fields_list, limit=6, order=f"{date_field} asc")
            items = []
            for record in records:
                case = record.get(case_field)
                court = record.get(court_field)
                items.append(
                    {
                        "id": record["id"],
                        "model": "qlk.hearing",
                        "name": record.get(name_field, ""),
                        "case": case[1] if isinstance(case, (list, tuple)) else "",
                        "court": court[1] if isinstance(court, (list, tuple)) else "",
                        "date": self._format_date_value(record.get(date_field), lang),
                        "state": record.get(state_field, "") if state_field else "",
                    }
                )
            lists["hearings"] = {
                "items": items,
                "action": self._action_dict("Hearings", "qlk.hearing", []),
            }

        assistant_requests = []
        if leave_model:
            leave_action = self._action_dict("Leave Requests", "hr.leave", [])
            leave_new = self._safe_count(leave_model, [("state", "in", ["draft", "confirm"])])
            leave_reviewed = self._safe_count(leave_model, [("state", "=", "validate1")])
            leave_escalated = self._safe_count(leave_model, [("state", "=", "validate")])
            assistant_requests.append(
                {
                    "key": "leave",
                    "label": "Leave Requests",
                    "new": leave_new,
                    "reviewed": leave_reviewed,
                    "escalated": leave_escalated,
                    "action": leave_action,
                }
            )

        if approval_model and "request_status" in approval_model._fields:
            approval_action = self._action_dict("HR Requests", "approval.request", [])
            approval_new = self._safe_count(approval_model, [("request_status", "=", "new")])
            approval_reviewed = self._safe_count(approval_model, [("request_status", "=", "pending")])
            approval_escalated = self._safe_count(approval_model, [("request_status", "=", "approved")])
            assistant_requests.append(
                {
                    "key": "hr",
                    "label": "HR Requests",
                    "new": approval_new,
                    "reviewed": approval_reviewed,
                    "escalated": approval_escalated,
                    "action": approval_action,
                }
            )

        if request_model and "state" in request_model._fields:
            request_action = self._action_dict("Internal Requests", "qlk.request", [])
            request_new = self._safe_count(request_model, [("state", "in", ["draft", "new", "submitted"])])
            request_reviewed = self._safe_count(request_model, [("state", "in", ["reviewed", "in_review"])])
            request_escalated = self._safe_count(request_model, [("state", "in", ["escalated", "approved"])])
            assistant_requests.append(
                {
                    "key": "internal",
                    "label": "Internal Requests",
                    "new": request_new,
                    "reviewed": request_reviewed,
                    "escalated": request_escalated,
                    "action": request_action,
                }
            )

        case_monitoring = {
            "delayed": {"count": 0, "action": None},
            "no_sessions": {"count": 0, "action": None},
            "upcoming_hearings": {"items": [], "action": None},
        }
        if case_model:
            if "next_hearing_date" in case_model._fields:
                delayed_domain = [("next_hearing_date", "<", today)]
                no_session_domain = [("next_hearing_date", "=", False)]
                case_monitoring["delayed"] = {
                    "count": self._safe_count(case_model, delayed_domain),
                    "action": self._action_dict("Delayed Cases", case_model._name, delayed_domain),
                }
                case_monitoring["no_sessions"] = {
                    "count": self._safe_count(case_model, no_session_domain),
                    "action": self._action_dict("Cases without Sessions", case_model._name, no_session_domain),
                }

        if hearing_model:
            upcoming_domain = [
                ("date", ">=", today),
                ("date", "<", today + timedelta(days=14)),
            ]
            upcoming_hearings = hearing_model.search(upcoming_domain, order="date asc", limit=6)
            case_monitoring["upcoming_hearings"] = {
                "items": [
                    {
                        "id": hearing.id,
                        "model": "qlk.hearing",
                        "name": hearing.name or "",
                        "case": hearing.case_id.name if hearing.case_id else "",
                        "court": hearing.case_group.name if getattr(hearing, "case_group", False) else "",
                        "date": format_date(self.env, hearing.date, lang_code=lang) if hearing.date else "",
                    }
                    for hearing in upcoming_hearings
                ],
                "action": self._action_dict("Upcoming Hearings", "qlk.hearing", upcoming_domain),
            }

        return {
            "user": {
                "name": user.name,
                "company": user.company_id.display_name if user.company_id else "",
            },
            "role": "manager" if is_manager else "assistant",
            "palette": palette,
            "manager": {
                "kpis": kpis,
                "approval_inbox": {
                    "items": manager_inbox[:6],
                    "action": self._action_dict(
                        "Approval Inbox",
                        approval_sources[0]["model"] if approval_sources else "bd.proposal",
                        [("state", "=", "waiting_manager_approval")],
                    ),
                },
                "pipeline": pipeline,
                "legal": legal_dashboard,
                "lists": lists,
            },
            "assistant": {
                "operational_requests": assistant_requests,
                "case_monitoring": case_monitoring,
                "pre_approval": {
                    "items": assistant_queue[:6],
                    "action": self._action_dict(
                        "Pre-Approval Queue",
                        approval_sources[0]["model"] if approval_sources else "bd.proposal",
                        [("state", "=", "waiting_manager_approval")],
                    ),
                },
                "lists": lists,
            },
        }

    @api.model
    def _ensure_group(self, group_xmlid):
        if self.env.user.has_group("base.group_system"):
            return
        if not self.env.user.has_group(group_xmlid):
            raise AccessError("You do not have permission to perform this action.")

    @api.model
    def _approval_model_config(self):
        return {
            "bd.proposal": {
                "approve_method": "action_manager_approve",
                "reject_method": "_apply_rejection_reason",
                "reject_role": "manager",
            },
            "bd.engagement.letter": {
                "approve_method": "action_manager_approve",
                "reject_method": "_apply_rejection_reason",
                "reject_role": "manager",
            },
        }

    @api.model
    def action_approve_record(self, model_name, res_id):
        self._ensure_group("qlk_executive_dashboard.group_qlk_executive_manager")
        config = self._approval_model_config().get(model_name)
        if not config:
            raise AccessError("Unsupported approval model.")
        record = self.env[model_name].browse(res_id)
        if not record.exists():
            raise AccessError("Record not found.")
        method_name = config.get("approve_method")
        method = getattr(record, method_name, False)
        if not method:
            raise AccessError("Approval method not available.")
        method()
        return True

    @api.model
    def action_reject_record(self, model_name, res_id, reason):
        self._ensure_group("qlk_executive_dashboard.group_qlk_executive_manager")
        reason = (reason or "").strip()
        if not reason:
            raise AccessError("Rejection reason is required.")
        config = self._approval_model_config().get(model_name)
        if not config:
            raise AccessError("Unsupported approval model.")
        record = self.env[model_name].browse(res_id)
        if not record.exists():
            raise AccessError("Record not found.")
        method_name = config.get("reject_method")
        method = getattr(record, method_name, False)
        if not method:
            raise AccessError("Rejection method not available.")
        method(reason, config.get("reject_role"))
        return True

    @api.model
    def action_assistant_recommend(self, model_name, res_id, recommendation, note=None):
        self._ensure_group("qlk_executive_dashboard.group_qlk_executive_assistant")
        record = self.env[model_name].browse(res_id)
        if not record.exists():
            raise AccessError("Record not found.")
        if not hasattr(record, "action_set_assistant_recommendation"):
            raise AccessError("Recommendation not supported for this model.")
        record.action_set_assistant_recommendation(recommendation, note or "")
        return True
