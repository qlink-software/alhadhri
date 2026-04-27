# -*- coding: utf-8 -*-

from odoo import _, api, models


class QlkCourtDashboardExtension(models.AbstractModel):
    _inherit = "qlk.court.dashboard"

    @api.model
    def _user_has_optional_group(self, user, xmlid):
        group = self.env.ref(xmlid, raise_if_not_found=False)
        return bool(group and group in user.groups_id)

    @api.model
    def _has_courts_dashboard_access(self, user):
        return bool(
            self._user_has_optional_group(user, "qlk_law_dashboard.group_qlk_law_dashboard_user")
            or self._user_has_optional_group(user, "qlk_law_dashboard.group_qlk_law_dashboard_manager")
            or self._user_has_optional_group(user, "qlk_law.group_courts_menu")
            or self._user_has_optional_group(user, "qlk_law.group_qlk_law_manager")
            or self._user_has_optional_group(user, "qlk_law.group_qlk_law_admin")
        )

    @api.model
    def _get_visible_courts(self, case_model, case_domain):
        court_groups = case_model.read_group(case_domain, ["court"], ["court"], lazy=False)
        return {group.get("court") for group in court_groups if group.get("court")}

    @api.model
    def _set_metric_payload(self, metrics, metric_key, model_name, domain, can_read=True):
        metric = (metrics or {}).get(metric_key)
        if not metric:
            return
        metric["domain"] = domain if can_read else []
        metric["count"] = self.env[model_name].search_count(domain) if can_read else 0
        if not can_read:
            metric["action"] = False

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        if not self._has_courts_dashboard_access(user):
            return {
                "cards": [],
                "labels": {
                    "dashboard": _("Courts Dashboard"),
                    "empty_title": _("Courts Dashboard"),
                    "empty_message": _("You do not have permission to view this dashboard."),
                },
            }

        data = super().get_dashboard_data()
        cards = data.get("cards") or []
        if not cards:
            return data

        case_model = self.env["qlk.case"]
        employee_ids = user.employee_ids.ids
        is_manager = self._is_manager(user)
        case_domain = self._model_domain(
            case_model, employee_ids, user, ["employee_id", "employee_ids"], is_manager
        )
        case_domain_active = self._merge_domain(case_domain, self.ACTIVE_CASE_DOMAIN)
        visible_courts = self._get_visible_courts(case_model, case_domain_active)

        hearing_model = self.env["qlk.hearing"]
        hearing_access = hearing_model.check_access_rights("read", raise_exception=False)
        hearing_domain = self._model_domain(
            hearing_model,
            employee_ids,
            user,
            ["employee_id", "employee2_id", "employee_ids"],
            is_manager,
        )

        memo_model = self.env["qlk.memo"]
        memo_access = memo_model.check_access_rights("read", raise_exception=False)
        memo_domain = self._model_domain(
            memo_model,
            employee_ids,
            user,
            ["employee_id", "employee2_id"],
            is_manager,
        )
        memo_domain = self._merge_domain(memo_domain, self.MEMO_DOMAIN)

        work_model = self.env["qlk.work"]
        work_access = work_model.check_access_rights("read", raise_exception=False)
        work_domain = self._model_domain(
            work_model, employee_ids, user, ["employee_id"], is_manager
        )
        work_domain = self._merge_domain(work_domain, self.ADMIN_TASK_DOMAIN)

        filtered_cards = []
        for card in cards:
            court_key = card.get("key")
            if court_key not in visible_courts:
                continue

            metrics = card.get("metrics") or {}
            case_metric_domain = self._merge_domain(case_domain_active, [("court", "=", court_key)])
            hearing_metric_domain = self._merge_domain(
                hearing_domain, [("case_group.court", "=", court_key)]
            )
            memo_metric_domain = self._merge_domain(
                memo_domain, [("case_group.court", "=", court_key)]
            )
            work_metric_domain = self._merge_domain(
                work_domain, [("case_group.court", "=", court_key)]
            )

            self._set_metric_payload(metrics, "cases", "qlk.case", case_metric_domain, can_read=True)
            self._set_metric_payload(
                metrics, "sessions", "qlk.hearing", hearing_metric_domain, can_read=hearing_access
            )
            self._set_metric_payload(
                metrics, "memos", "qlk.memo", memo_metric_domain, can_read=memo_access
            )
            self._set_metric_payload(
                metrics, "admin_tasks", "qlk.work", work_metric_domain, can_read=work_access
            )
            filtered_cards.append(card)

        data["cards"] = filtered_cards
        if not filtered_cards:
            labels = data.get("labels") or {}
            labels.update(
                {
                    "empty_title": _("Courts Dashboard"),
                    "empty_message": _("No court data available for your permissions."),
                }
            )
            data["labels"] = labels
        return data
