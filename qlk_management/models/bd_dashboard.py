# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.tools.misc import format_amount


class QlkBusinessDevelopmentDashboard(models.AbstractModel):
    _name = "qlk.bd.dashboard"
    _description = "Business Development Dashboard Service"

    def _action_payload(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        return {"id": action.id} if action else None

    def _format_currency(self, amount):
        currency = self.env.company.currency_id
        return format_amount(self.env, amount or 0.0, currency)

    def _build_group_cards(self, model, groups, base_domain=None):
        base_domain = base_domain or []
        total = model.search_count(base_domain)
        cards = []
        for group in groups:
            domain = base_domain + group["domain"]
            count = model.search_count(domain)
            percent = round((count / total) * 100) if total else 0
            cards.append(
                {
                    "key": group["key"],
                    "label": group["label"],
                    "count": count,
                    "percent": percent,
                    "tone": group.get("tone", "primary"),
                    "domain": domain,
                }
            )
        return cards, total

    def _project_state_groups(self, project_model):
        base_domain = []
        if "active" in project_model._fields:
            base_domain.append(("active", "=", True))

        if "state" in project_model._fields:
            in_progress_domain = [("state", "=", "open")]
            done_domain = [("state", "=", "close")]
            on_hold_domain = [("state", "=", "open")]
        else:
            in_progress_domain = [("id", "=", 0)]
            on_hold_domain = [("id", "=", 0)]
            done_domain = [("id", "=", 0)]

        return self._build_group_cards(
            project_model,
            [
                {"key": "in_progress", "label": _("In Progress"), "domain": in_progress_domain, "tone": "primary"},
                {"key": "on_hold", "label": _("On Hold"), "domain": on_hold_domain, "tone": "warning"},
                {"key": "done", "label": _("Done / Closed"), "domain": done_domain, "tone": "success"},
            ],
            base_domain=base_domain,
        )

    def _opportunity_state_groups(self, opportunity_model):
        domain = [("type", "=", "opportunity")]
        state_groups = opportunity_model.read_group(domain, ["state"], ["state"], lazy=False)
        state_labels = dict(opportunity_model._fields["state"].selection or [])
        cards = []
        total = opportunity_model.search_count(domain)
        for group in state_groups:
            state_value = group.get("state")
            if not state_value:
                continue
            if state_value == "send":
                tone = "success"
            elif state_value == "not_interested":
                tone = "danger"
            elif state_value == "follow_up":
                tone = "warning"
            else:
                tone = "primary"
            count = group.get("state_count", group.get("__count", 0))
            percent = round((count / total) * 100) if total else 0
            cards.append(
                {
                    "key": f"state_{state_value}",
                    "label": state_labels.get(state_value, state_value),
                    "count": count,
                    "percent": percent,
                    "tone": tone,
                    "domain": domain + [("state", "=", state_value)],
                }
            )
        return cards, total

    @api.model
    def get_dashboard_data(self):
        proposal_model = self.env["bd.proposal"]
        engagement_model = self.env["bd.engagement.letter"]
        opportunity_model = self.env["crm.lead"]
        project_model = self.env["project.project"]

        proposal_action = self._action_payload("qlk_management.action_bd_proposal") or self._action_payload(
            "qlk_management.action_proposal"
        )
        engagement_action = self._action_payload("qlk_management.action_bd_engagement_letter")
        opportunity_action = self._action_payload("crm.crm_lead_action_pipeline")
        project_action = self._action_payload("qlk_management.action_qlk_project") or self._action_payload(
            "project.open_view_project_all"
        )

        proposal_groups, proposal_total = self._build_group_cards(
            proposal_model,
            [
                {"key": "draft", "label": _("Draft"), "domain": [("state", "=", "draft")], "tone": "primary"},
                {
                    "key": "waiting_manager",
                    "label": _("Waiting Manager Approval"),
                    "domain": [("state", "=", "waiting_manager_approval")],
                    "tone": "warning",
                },
                {
                    "key": "waiting_client",
                    "label": _("Waiting Client Approval"),
                    "domain": [("state", "=", "waiting_client_approval")],
                    "tone": "warning",
                },
                {
                    "key": "approved",
                    "label": _("Approved"),
                    "domain": [("state", "=", "approved_client")],
                    "tone": "success",
                },
                {
                    "key": "rejected",
                    "label": _("Rejected / Cancelled"),
                    "domain": [("state", "in", ["rejected", "cancelled"])],
                    "tone": "danger",
                },
            ],
        )

        engagement_groups, engagement_total = self._build_group_cards(
            engagement_model,
            [
                {"key": "draft", "label": _("Draft"), "domain": [("state", "=", "draft")], "tone": "primary"},
                {
                    "key": "waiting_manager",
                    "label": _("Waiting Manager Approval"),
                    "domain": [("state", "=", "waiting_manager_approval")],
                    "tone": "warning",
                },
                {
                    "key": "waiting_client",
                    "label": _("Waiting Client Approval"),
                    "domain": [("state", "=", "waiting_client_approval")],
                    "tone": "warning",
                },
                {
                    "key": "approved",
                    "label": _("Approved"),
                    "domain": [("state", "=", "approved_client")],
                    "tone": "success",
                },
                {
                    "key": "rejected",
                    "label": _("Rejected / Cancelled"),
                    "domain": [("state", "in", ["rejected", "cancelled"])],
                    "tone": "danger",
                },
            ],
        )

        opportunity_groups, opportunity_total = self._opportunity_state_groups(opportunity_model)

        project_groups, project_total = self._project_state_groups(project_model)

        return {
            "palette": {
                "primary": "#0F5CA8",
                "accent": "#22B6C8",
                "muted": "#0D3E7A",
                "success": "#27AE60",
                "warning": "#F39C12",
                "danger": "#C0392B",
            },
            "kpis": {
                "opportunities": opportunity_total,
                "proposals": proposal_total,
                "engagements": engagement_total,
                "projects": project_total,
            },
            "sections": [
                {
                    "key": "opportunities",
                    "title": _("Opportunities"),
                    "subtitle": _("Pipeline health by stage"),
                    "action": opportunity_action,
                    "groups": opportunity_groups,
                },
                {
                    "key": "proposals",
                    "title": _("Proposals"),
                    "subtitle": _("BD proposals workflow"),
                    "action": proposal_action,
                    "groups": proposal_groups,
                },
                {
                    "key": "engagements",
                    "title": _("Engagement Letters"),
                    "subtitle": _("Contract approvals"),
                    "action": engagement_action,
                    "groups": engagement_groups,
                },
                {
                    "key": "projects",
                    "title": _("Projects"),
                    "subtitle": _("Delivery execution status"),
                    "action": project_action,
                    "groups": project_groups,
                },
            ],
        }
