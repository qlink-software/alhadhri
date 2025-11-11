# -*- coding: utf-8 -*-
from datetime import date, datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.osv.expression import OR
from odoo.tools.misc import format_date


class CorporateDashboard(models.AbstractModel):
    _name = "qlk.corporate.dashboard"
    _description = "Corporate Department Dashboard Service"

    def _palette(self):
        return {
            "primary": "#00457E",
            "accent": "#31C3A2",
            "muted": "#0B1F3A",
            "warning": "#F39C12",
            "success": "#2ECC71",
        }

    def _is_manager(self, user):
        return user.has_group("qlk_law.group_qlk_law_manager") or user.has_group("base.group_system")

    def _corporate_user_domain(self, user):
        if self._is_manager(user):
            return []
        employee_ids = user.employee_ids.ids
        clauses = []
        if employee_ids:
            clauses.append(("responsible_employee_id", "in", employee_ids))
        clauses.append(("responsible_user_id", "=", user.id))
        if len(clauses) == 1:
            return clauses
        # Build OR domain for clauses while respecting Odoo postfix notation
        domain = []
        for clause in clauses:
            if not domain:
                domain.append(clause)
            else:
                domain = ["|"] + domain + [clause]
        return domain

    def _task_domain(self, user):
        domain = [
            ("department", "=", "corporate"),
            ("approval_state", "=", "approved"),
        ]
        if self._is_manager(user):
            return domain
        employee_ids = user.employee_ids.ids
        clauses = []
        if employee_ids:
            clauses.append(("employee_id", "in", employee_ids))
        clauses.append(("assigned_user_id", "=", user.id))
        if len(clauses) == 1:
            domain.append(clauses[0])
        else:
            ors = ["|"] * (len(clauses) - 1)
            domain.extend(ors + clauses)
        return domain

    def _format_case(self, case, lang):
        return {
            "id": case.id,
            "name": case.name,
            "client": case.client_id.name or "",
            "service": dict(case._fields["service_type"].selection).get(case.service_type, case.service_type),
            "status": dict(case._fields["state"].selection).get(case.state, case.state),
            "next_deadline": case.agreement_end_date and format_date(self.env, case.agreement_end_date, lang_code=lang) or "",
            "url": {"res_model": "qlk.corporate.case", "res_id": case.id},
        }

    def _format_consultation(self, consultation, lang):
        return {
            "id": consultation.id,
            "name": consultation.name,
            "case": consultation.case_id.name if consultation.case_id else "",
            "date": consultation.consultation_date
            and format_date(self.env, consultation.consultation_date, lang_code=lang)
            or "",
            "fee_amount": consultation.fee_amount,
            "status": dict(consultation._fields["state"].selection).get(consultation.state, consultation.state),
            "url": {"res_model": "qlk.corporate.consultation", "res_id": consultation.id},
        }

    def _format_contract(self, contract, lang):
        return {
            "id": contract.id,
            "name": contract.name,
            "case": contract.case_id.name if contract.case_id else "",
            "type": dict(contract._fields["contract_type"].selection).get(contract.contract_type, contract.contract_type),
            "start_date": contract.start_date and format_date(self.env, contract.start_date, lang_code=lang) or "",
            "end_date": contract.end_date and format_date(self.env, contract.end_date, lang_code=lang) or "",
            "url": {"res_model": "qlk.corporate.contract", "res_id": contract.id},
        }

    def _format_document(self, document, lang):
        return {
            "id": document.id,
            "name": document.name,
            "case": document.case_id.name if document.case_id else "",
            "type": dict(document._fields["document_type"].selection).get(document.document_type, document.document_type),
            "issue_date": document.issue_date and format_date(self.env, document.issue_date, lang_code=lang) or "",
            "url": {"res_model": "qlk.corporate.document", "res_id": document.id},
        }

    def _date_range(self):
        today = fields.Date.context_today(self)
        start_week = today - relativedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)
        return today, start_week, end_week

    def _datetime_bounds(self, day):
        return (
            fields.Datetime.to_string(datetime.combine(day, time.min)),
            fields.Datetime.to_string(datetime.combine(day + timedelta(days=1), time.min)),
        )

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        lang = user.lang or "en_US"
        corporate_case_model = self.env["qlk.corporate.case"]
        consultation_model = self.env["qlk.corporate.consultation"]
        contract_model = self.env["qlk.corporate.contract"]
        document_model = self.env["qlk.corporate.document"]
        task_model = self.env["qlk.task"]

        today, start_week, end_week = self._date_range()
        start_week_dt = fields.Datetime.to_string(datetime.combine(start_week, time.min))
        end_week_dt = fields.Datetime.to_string(datetime.combine(end_week + timedelta(days=1), time.min))
        today_start, tomorrow_start = self._datetime_bounds(today)

        case_domain = self._corporate_user_domain(user)
        cases = corporate_case_model.search(case_domain, order="write_date desc", limit=10)
        accessible_case_ids = corporate_case_model.search(case_domain).ids if case_domain else corporate_case_model.search([]).ids
        case_filter = [("case_id", "in", accessible_case_ids)] if accessible_case_ids else [("case_id", "=", False)]

        cases_total = corporate_case_model.search_count(case_domain)
        cases_today = corporate_case_model.search_count(case_domain + [("create_date", ">=", today_start), ("create_date", "<", tomorrow_start)])
        cases_week = corporate_case_model.search_count(case_domain + [("create_date", ">=", start_week_dt), ("create_date", "<", end_week_dt)])

        consultations_today = consultation_model.search_count(
            case_filter + [("consultation_date", "=", today)]
        )
        consultations_week = consultation_model.search_count(
            case_filter + [("consultation_date", ">=", start_week), ("consultation_date", "<=", end_week)]
        )

        contracts_week = contract_model.search_count(
            case_filter + [
                ("start_date", "!=", False),
                ("start_date", ">=", start_week),
                ("start_date", "<=", end_week),
            ]
        )
        documents_week = document_model.search_count(
            case_filter + [
                ("issue_date", "!=", False),
                ("issue_date", ">=", start_week),
                ("issue_date", "<=", end_week),
            ]
        )

        upcoming_consultations = consultation_model.search(
            case_filter
            + [
                ("consultation_date", ">=", today),
            ],
            order="consultation_date asc",
            limit=10,
        )

        recent_contracts = contract_model.search(
            case_filter,
            order="write_date desc",
            limit=10,
        )

        recent_documents = document_model.search(
            case_filter,
            order="issue_date desc, write_date desc",
            limit=10,
        )

        task_domain = self._task_domain(user)

        hours_total = 0.0
        hours_week = 0.0
        hours_today = 0.0

        total_group = task_model.read_group(task_domain, ["hours_spent"], [])
        if total_group:
            hours_total = total_group[0].get("hours_spent", 0.0) or 0.0

        week_group = task_model.read_group(
            task_domain + [("date_start", ">=", start_week), ("date_start", "<=", end_week)],
            ["hours_spent"],
            [],
        )
        if week_group:
            hours_week = week_group[0].get("hours_spent", 0.0) or 0.0

        today_group = task_model.read_group(
            task_domain + [("date_start", "=", today)],
            ["hours_spent"],
            [],
        )
        if today_group:
            hours_today = today_group[0].get("hours_spent", 0.0) or 0.0

        actions = {
            "cases": self.env.ref("qlk_corporate.action_corporate_case", raise_if_not_found=False),
            "consultations": self.env.ref("qlk_corporate.action_corporate_consultation", raise_if_not_found=False),
            "contracts": self.env.ref("qlk_corporate.action_corporate_contract", raise_if_not_found=False),
            "documents": self.env.ref("qlk_corporate.action_corporate_document", raise_if_not_found=False),
        }

        action_payload = {key: {"id": action.id} for key, action in actions.items() if action}

        return {
            "palette": self._palette(),
            "user": {
                "name": user.name,
                "company": user.company_id.name if user.company_id else "",
            },
            "is_manager": self._is_manager(user),
            "metrics": {
                "cases_total": cases_total,
                "cases_today": cases_today,
                "cases_week": cases_week,
                "consultations_today": consultations_today,
                "consultations_week": consultations_week,
                "contracts_week": contracts_week,
                "documents_week": documents_week,
                "hours_total": round(hours_total, 2),
                "hours_week": round(hours_week, 2),
                "hours_today": round(hours_today, 2),
                "week_range": {
                    "start": format_date(self.env, start_week, lang_code=lang),
                    "end": format_date(self.env, end_week, lang_code=lang),
                },
                "today_label": format_date(self.env, today, lang_code=lang),
            },
            "lists": {
                "recent_cases": [self._format_case(case, lang) for case in cases],
                "upcoming_consultations": [self._format_consultation(rec, lang) for rec in upcoming_consultations],
                "recent_contracts": [self._format_contract(rec, lang) for rec in recent_contracts],
                "recent_documents": [self._format_document(rec, lang) for rec in recent_documents],
            },
            "actions": action_payload,
        }
