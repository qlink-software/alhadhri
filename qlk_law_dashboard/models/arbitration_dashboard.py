# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools.misc import format_date


class ArbitrationDashboard(models.AbstractModel):
    _name = "qlk.arbitration.dashboard"
    _description = "Arbitration Department Dashboard Service"

    def _palette(self):
        return {
            "primary": "#6C2BD9",
            "accent": "#9F7AEA",
            "muted": "#321C64",
            "warning": "#E2A72E",
            "success": "#48BB78",
        }

    def _is_manager(self, user):
        return user.has_group("qlk_arbitration.group_arbitration_manager") or user.has_group("base.group_system")

    def _case_domain(self, user):
        if self._is_manager(user):
            return []
        employee_ids = user.employee_ids.ids
        domain = []
        if employee_ids:
            domain = ["|"] * (len(employee_ids)) if employee_ids else []
        clauses = []
        if employee_ids:
            clauses.append(("responsible_employee_id", "in", employee_ids))
        clauses.append(("responsible_user_id", "=", user.id))
        if len(clauses) == 1:
            return clauses
        result = []
        for clause in clauses:
            if not result:
                result.append(clause)
            else:
                result = ["|"] + result + [clause]
        return result

    def _format_case(self, case, lang):
        return {
            "id": case.id,
            "name": case.name,
            "case_number": case.case_number or "",
            "center": case.arbitration_center or "",
            "state": dict(case._fields["state"].selection).get(case.state, case.state),
            "url": {"res_model": "qlk.arbitration.case", "res_id": case.id},
        }

    def _format_session(self, session, lang):
        return {
            "id": session.id,
            "name": session.name,
            "case": session.case_id.name if session.case_id else "",
            "date": session.session_date and format_date(self.env, fields.Date.to_date(session.session_date), lang_code=lang) or "",
            "arbitrator": session.arbitrator_id.name if session.arbitrator_id else "",
            "url": {"res_model": "qlk.arbitration.session", "res_id": session.id},
        }

    def _format_memo(self, memo):
        return {
            "id": memo.id,
            "name": memo.name,
            "case": memo.case_id.name if memo.case_id else "",
            "type": dict(memo._fields["memo_type"].selection).get(memo.memo_type, memo.memo_type),
            "date": memo.submission_date,
            "url": {"res_model": "qlk.arbitration.memo", "res_id": memo.id},
        }

    def _format_award(self, award):
        return {
            "id": award.id,
            "name": award.name,
            "case": award.case_id.name if award.case_id else "",
            "date": award.decision_date,
            "enforcement_body": award.enforcement_body or "",
            "url": {"res_model": "qlk.arbitration.award", "res_id": award.id},
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

        case_model = self.env["qlk.arbitration.case"]
        session_model = self.env["qlk.arbitration.session"]
        memo_model = self.env["qlk.arbitration.memo"]
        award_model = self.env["qlk.arbitration.award"]

        today, week_start, week_end = self._date_range()
        today_start, tomorrow_start = self._datetime_bounds(today)
        week_start_dt = fields.Datetime.to_string(datetime.combine(week_start, time.min))
        week_end_dt = fields.Datetime.to_string(datetime.combine(week_end + timedelta(days=1), time.min))

        domain = self._case_domain(user)
        cases = case_model.search(domain, order="write_date desc", limit=10)
        case_ids = case_model.search(domain).ids if domain else case_model.search([]).ids

        cases_total = case_model.search_count(domain)
        cases_month = case_model.search_count(domain + [("create_date", ">=", week_start_dt)])

        session_domain = [
            ("case_id", "in", case_ids),
        ] if case_ids else [("id", "=", False)]

        sessions_week = session_model.search_count(session_domain + [("session_date", ">=", week_start_dt), ("session_date", "<", week_end_dt)])
        sessions_today = session_model.search(session_domain + [("session_date", ">=", today_start), ("session_date", "<", tomorrow_start)], order="session_date asc")

        memos_week = memo_model.search_count([("case_id", "in", case_ids), ("submission_date", ">=", week_start), ("submission_date", "<=", week_end)]) if case_ids else 0
        awards_week = award_model.search_count([("case_id", "in", case_ids), ("decision_date", ">=", week_start), ("decision_date", "<=", week_end)]) if case_ids else 0

        recent_sessions = session_model.search(session_domain, order="session_date desc", limit=10)
        recent_memos = memo_model.search([("case_id", "in", case_ids)], order="submission_date desc", limit=10) if case_ids else memo_model.browse([])
        recent_awards = award_model.search([("case_id", "in", case_ids)], order="decision_date desc", limit=10) if case_ids else award_model.browse([])

        actions = {
            "cases": self.env.ref("qlk_arbitration.action_arbitration_case", raise_if_not_found=False),
            "sessions": self.env.ref("qlk_arbitration.action_arbitration_session", raise_if_not_found=False),
            "memos": self.env.ref("qlk_arbitration.action_arbitration_memo", raise_if_not_found=False),
            "awards": self.env.ref("qlk_arbitration.action_arbitration_award", raise_if_not_found=False),
            "arbitrators": self.env.ref("qlk_arbitration.action_arbitrator_register", raise_if_not_found=False),
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
                "cases_month": cases_month,
                "sessions_week": sessions_week,
                "memos_week": memos_week,
                "awards_week": awards_week,
                "today_label": format_date(self.env, today, lang_code=lang),
                "week_range": {
                    "start": format_date(self.env, week_start, lang_code=lang),
                    "end": format_date(self.env, week_end, lang_code=lang),
                },
            },
            "lists": {
                "recent_cases": [self._format_case(case, lang) for case in cases],
                "upcoming_sessions": [self._format_session(session, lang) for session in sessions_today],
                "recent_sessions": [self._format_session(session, lang) for session in recent_sessions],
                "recent_memos": [self._format_memo(memo) for memo in recent_memos],
                "recent_awards": [self._format_award(award) for award in recent_awards],
            },
            "actions": action_payload,
        }
