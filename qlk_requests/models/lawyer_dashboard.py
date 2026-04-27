# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.tools.misc import format_date


class LawyerDashboardRequests(models.AbstractModel):
    _inherit = "qlk.lawyer.dashboard"

    @api.model
    def _request_action_payload(self, xmlid="qlk_requests.action_qlk_request"):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        return {"id": action.id} if action else False

    @api.model
    def _selection_label(self, record, field_name):
        parent_method = getattr(super(), "_selection_label", None)
        if callable(parent_method):
            return parent_method(record, field_name)
        field = record._fields.get(field_name)
        selection = field.selection if field else []
        if callable(selection):
            selection = selection(record)
        return dict(selection or []).get(record[field_name], record[field_name] or "")

    @api.model
    def _get_request_bucket(self, domain, lang, action_xmlid="qlk_requests.action_qlk_request", include_items=True):
        Request = self.env["qlk.internal.request"]
        action = self._request_action_payload(action_xmlid)
        breakdown = {}
        for state in ("draft", "submitted", "in_progress", "done", "cancelled"):
            breakdown[state] = Request.search_count(domain + [("state", "=", state)])

        items = []
        if include_items:
            requests = Request.search(domain, order="request_date desc, id desc", limit=5)
            for request in requests:
                items.append(
                    {
                        "id": request.id,
                        "name": request.display_name,
                        "from_user": request.requested_by.name or "",
                        "to_user": request.assigned_to.name or "",
                        "date": request.request_date and format_date(self.env, request.request_date, lang_code=lang) or "",
                        "state": request.state,
                        "state_label": self._selection_label(request, "state"),
                        "priority": request.priority or "",
                        "url": {"res_model": "qlk.internal.request", "res_id": request.id},
                    }
                )

        return {
            "count": Request.search_count(domain),
            "breakdown": breakdown,
            "domain": domain,
            "action": action,
            "items": items,
        }

    @api.model
    def _get_requests_dashboard_payload(self, lang):
        if "qlk.internal.request" not in self.env:
            return {}
        Request = self.env["qlk.internal.request"]
        if not Request.check_access_rights("read", raise_exception=False):
            return {}

        user = self.env.user
        my_domain = [("requested_by", "=", user.id)]
        assigned_domain = [("assigned_to", "=", user.id)]
        return {
            "my": self._get_request_bucket(
                my_domain,
                lang,
                action_xmlid="qlk_requests.action_qlk_request_my",
            ),
            "assigned": self._get_request_bucket(
                assigned_domain,
                lang,
                action_xmlid="qlk_requests.action_qlk_request_assigned_to_me",
                include_items=False,
            ),
        }

    @api.model
    def get_dashboard_data(self):
        data = super().get_dashboard_data()
        lang = self.env.user.lang or self.env.context.get("lang")
        labels = data.get("labels") or {}
        labels.update(
            {
                "requests_title": _("الطلبات"),
                "requests_subtitle": _("متابعة الطلبات الداخلية بين المستخدمين."),
                "my_requests_title": _("طلباتي"),
                "assigned_requests_title": _("الطلبات الموكلة لي"),
                "request_name_title": _("Name"),
                "request_from_title": _("From"),
                "request_to_title": _("To"),
                "request_date_title": _("Date"),
                "request_status_title": _("Status"),
                "request_draft_title": _("Draft"),
                "request_sent_title": _("Submitted"),
                "request_progress_title": _("In Progress"),
                "request_done_title": _("Done"),
                "request_cancelled_title": _("Cancelled"),
                "view_requests": _("View All"),
                "no_requests": _("لا توجد طلبات مطابقة."),
            }
        )
        data["labels"] = labels
        data["requests_dashboard"] = self._get_requests_dashboard_payload(lang)
        return data
