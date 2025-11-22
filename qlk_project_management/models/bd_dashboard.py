# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.tools.misc import format_amount, format_date


class QlkBusinessDevelopmentDashboard(models.AbstractModel):
    _name = "qlk.bd.dashboard"
    _description = "Business Development Dashboard Service"

    def _action_payload(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        return {"id": action.id} if action else None

    def _format_currency(self, amount):
        currency = self.env.company.currency_id
        return format_amount(self.env, amount or 0.0, currency)

    def _format_date(self, value, lang):
        if not value:
            return "-"
        if isinstance(value, datetime):
            value = value.date()
        return format_date(self.env, value, lang_code=lang)

    def _expiration_badge(self, expires_on):
        if not expires_on:
            return _("No expiry"), "badge--muted"
        today = fields.Date.context_today(self)
        target = expires_on if not isinstance(expires_on, str) else fields.Date.from_string(expires_on)
        delta = (target - today).days
        if delta < 0:
            return _("Expired"), "badge--danger"
        if delta <= 15:
            return _("Due in %s d") % delta, "badge--warning"
        if delta <= 30:
            return _("Due in %s d") % delta, "badge--info"
        return _("In %s days") % delta, "badge--success"

    @api.model
    def get_dashboard_data(self):
        lang = self.env.user.lang or "en_US"
        proposal_model = self.env["sale.order"]
        agreement_model = self.env["managment.agreement"]
        partner_model = self.env["res.partner"]
        document_model = self.env.get("qlk.client.document")

        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_start_dt = datetime.combine(month_start, datetime.min.time())

        proposal_domain = [("is_proposal", "=", True)]
        pipeline_domain = proposal_domain + [("state", "not in", ["sale", "done", "cancel"])]
        pipeline_group = proposal_model.read_group(pipeline_domain, ["amount_total"], [])
        pipeline_value = pipeline_group[0]["amount_total"] if pipeline_group else 0.0
        pipeline_count = proposal_model.search_count(pipeline_domain)

        agreements_month = agreement_model.search_count([("create_date", ">=", fields.Datetime.to_string(month_start_dt))])
        clients_total = partner_model.search_count([("customer_rank", ">", 0)])

        doc_action = None
        doc_labels = {}
        expiring_docs = []
        expires_by = today + timedelta(days=45)
        expiring_domain = [
            ("poa_expiration_date", "!=", False),
            ("poa_expiration_date", "<=", fields.Date.to_string(expires_by)),
        ]
        expiring_total = 0
        clients_with_documents = 0
        if document_model:
            doc_action = self._action_payload("qlk_management.action_client_documents")
            doc_labels = dict(document_model._fields["doc_type"].selection)
            expiring_docs = document_model.search(expiring_domain, order="poa_expiration_date asc", limit=10)
            expiring_total = document_model.search_count([("poa_expiration_date", "!=", False)])
            clients_with_documents = document_model.read_group([], ["partner_id"], ["partner_id"])
            clients_with_documents = len(clients_with_documents)

        actions = {
            "proposals": self._action_payload("qlk_management.action_proposal"),
            "agreements": self._action_payload("qlk_management.managment_agreement_action"),
            "documents": doc_action,
            "contacts": self._action_payload("contacts.action_contacts"),
        }

        pipeline_records = []
        stage_selection = dict(proposal_model._fields["state"].selection)
        pipeline = proposal_model.search(pipeline_domain, order="priority desc, write_date desc", limit=8)
        for record in pipeline:
            pipeline_records.append(
                {
                    "id": record.id,
                    "name": record.proposal_seq or record.name,
                    "client": record.partner_id.display_name or record.client_name or "",
                    "stage": stage_selection.get(record.state, record.state),
                    "amount_display": self._format_currency(record.amount_total),
                    "date": self._format_date(record.date_order, lang),
                    "url": {"res_model": "sale.order", "res_id": record.id},
                }
            )

        agreement_records = []
        agreement_selection = dict(agreement_model._fields["agreement_state"].selection)
        agreements = agreement_model.search([], order="write_date desc", limit=8)
        for agreement in agreements:
            agreement_records.append(
                {
                    "id": agreement.id,
                    "name": agreement.agrement_seq or agreement.display_name,
                    "client": agreement.client_id.display_name if agreement.client_id else "",
                    "status": agreement_selection.get(agreement.agreement_state, agreement.agreement_state),
                    "start": self._format_date(agreement.start_date, lang),
                    "end": self._format_date(agreement.end_date, lang),
                    "url": {"res_model": "managment.agreement", "res_id": agreement.id},
                }
            )

        document_records = []
        for document in expiring_docs:
            label, badge = self._expiration_badge(document.poa_expiration_date)
            document_records.append(
                {
                    "id": document.id,
                    "partner": document.partner_id.display_name if document.partner_id else "",
                    "doc_type": doc_labels.get(document.doc_type, document.doc_type),
                    "expires": self._format_date(document.poa_expiration_date, lang),
                    "status": label,
                    "status_class": badge,
                    "url": {"res_model": "qlk.client.document", "res_id": document.id},
                }
            )

        followup_domain = proposal_domain + [("state", "in", ("approve", "sent"))]
        followup_items = []
        followups = proposal_model.search(followup_domain, order="validity_date asc, write_date asc", limit=8)
        for record in followups:
            deadline = self._format_date(record.validity_date, lang) if record.validity_date else _("No deadline")
            followup_items.append(
                {
                    "id": record.id,
                    "title": record.proposal_seq or record.name,
                    "client": record.partner_id.display_name or record.client_name or "",
                    "deadline": deadline,
                    "stage": stage_selection.get(record.state, record.state),
                    "url": {"res_model": "sale.order", "res_id": record.id},
                }
            )

        summary_cards = [
            {
                "title": _("Pipeline Value"),
                "value": self._format_currency(pipeline_value),
                "caption": _("%s open deals") % pipeline_count,
            },
            {
                "title": _("Signed this month"),
                "value": str(agreements_month),
                "caption": format_date(self.env, month_start, lang_code=lang),
            },
            {
                "title": _("Clients with POA"),
                "value": str(clients_with_documents),
                "caption": _("Active customers: %s") % clients_total,
            },
            {
                "title": _("Expiring documents"),
                "value": str(expiring_total),
                "caption": _("Within the next 45 days"),
            },
        ]

        return {
            "palette": {
                "primary": "#0d1b2a",
                "accent": "#1b263b",
                "muted": "#415a77",
                "success": "#22c55e",
            },
            "summary": summary_cards,
            "pipeline": {
                "title": _("Pipeline Watch"),
                "records": pipeline_records,
                "action": actions["proposals"],
                "domain": pipeline_domain,
            },
            "agreements": {
                "title": _("Recently Signed"),
                "records": agreement_records,
                "action": actions["agreements"],
            },
            "documents": {
                "title": _("Document Alerts"),
                "records": document_records,
                "action": actions["documents"],
                "domain": expiring_domain,
            },
            "followups": {
                "title": _("Follow-ups"),
                "items": followup_items,
                "action": actions["proposals"],
                "domain": followup_domain,
            },
        }
