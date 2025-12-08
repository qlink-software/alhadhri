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
        proposal_model = self.env["bd.proposal"]
        engagement_model = self.env["bd.engagement.letter"]
        partner_model = self.env["res.partner"]
        document_model = self.env.get("qlk.client.document")
        today = fields.Date.context_today(self)
        client_domain = [("customer_rank", ">", 0)]

        proposals_total = proposal_model.search_count([])
        proposals_approved = proposal_model.search_count([("state", "in", ("approved", "client_approved"))])
        clients_total = partner_model.search_count(client_domain)

        documents_total = document_model.search_count([]) if document_model else 0
        expiring_total = 0

        pipeline_states = ("draft", "waiting_approval", "approved")
        pipeline_domain = [("state", "in", pipeline_states)]
        pipeline_value = proposal_model.read_group(pipeline_domain, ["legal_fees:sum"], [])
        pipeline_amount = pipeline_value[0]["legal_fees_sum"] if pipeline_value else 0.0
        pipeline_count = proposal_model.search_count(pipeline_domain)

        doc_labels = {}
        document_types = []
        expiring_records = []
        expiring_domain = []
        if document_model:
            doc_labels = dict(document_model._fields["doc_type"].selection)
            expires_by = today + timedelta(days=45)
            expiring_domain = [
                ("poa_expiration_date", "!=", False),
                ("poa_expiration_date", "<=", fields.Date.to_string(expires_by)),
            ]
            expiring_total = document_model.search_count([("poa_expiration_date", "!=", False)])
            doc_groups = document_model.read_group([], ["doc_type", "poa_expiration_date:min"], ["doc_type"])
            for group in doc_groups:
                doc_type = group.get("doc_type")
                if not doc_type:
                    continue
                expiry_value = group.get("poa_expiration_date_min")
                status_label, status_css = self._expiration_badge(expiry_value)
                document_types.append(
                    {
                        "type": doc_type,
                        "label": doc_labels.get(doc_type, doc_type),
                        "count": group.get("__count", 0),
                        "next_expiry": self._format_date(expiry_value, lang),
                        "status": status_label,
                        "status_class": status_css,
                    }
                )
            expiring_docs = document_model.search(expiring_domain, order="poa_expiration_date asc", limit=10)
            for document in expiring_docs:
                label, badge = self._expiration_badge(document.poa_expiration_date)
                expiring_records.append(
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

        client_action = self._action_payload("qlk_management.action_bd_client_data")
        client_cards = []
        partners = partner_model.search(client_domain, order="poa_next_expiration_date asc, write_date desc", limit=8)
        for partner in partners:
            status_label, status_css = self._expiration_badge(partner.poa_next_expiration_date)
            documents = []
            for document in partner.client_document_ids:
                documents.append(
                    {
                        "label": doc_labels.get(document.doc_type, document.doc_type),
                        "expires": self._format_date(document.poa_expiration_date, lang),
                        "uploaded": document.is_uploaded,
                    }
                )
            client_cards.append(
                {
                    "id": partner.id,
                    "name": partner.display_name,
                    "code": partner.bd_client_code,
                    "type": partner.company_type,
                    "status": status_label,
                    "status_class": status_css,
                    "expiry": self._format_date(partner.poa_next_expiration_date, lang),
                    "warning": bool(partner.document_warning_required),
                    "documents": documents,
                    "url": {"res_model": "res.partner", "res_id": partner.id},
                }
            )

        proposal_action = self._action_payload("qlk_management.action_bd_proposal") or self._action_payload(
            "qlk_management.action_proposal"
        )
        proposal_state_labels = dict(proposal_model._fields["state"].selection)
        proposal_states = proposal_model.read_group([], ["state"], ["state"])
        proposal_state_cards = []
        for entry in proposal_states:
            state_value = entry.get("state")
            if not state_value:
                continue
            domain = [("state", "=", state_value)]
            proposal_state_cards.append(
                {
                    "key": state_value,
                    "label": proposal_state_labels.get(state_value, state_value),
                    "count": entry.get("state_count", entry.get("__count", 0)),
                    "domain": domain,
                }
            )
        proposal_items = proposal_model.search([], order="write_date desc", limit=8)
        proposal_records = []
        for proposal in proposal_items:
            proposal_records.append(
                {
                    "id": proposal.id,
                    "title": proposal.name,
                    "client": proposal.partner_id.display_name or proposal.client_name or "",
                    "state": proposal_state_labels.get(proposal.state, proposal.state),
                    "amount": self._format_currency(proposal.legal_fees),
                    "url": {"res_model": "bd.proposal", "res_id": proposal.id},
                }
            )

        engagement_action = self._action_payload("qlk_management.action_bd_engagement_letter")
        engagement_state_labels = dict(engagement_model._fields["state"].selection)
        engagement_states = engagement_model.read_group([], ["state"], ["state"])
        engagement_state_cards = []
        for entry in engagement_states:
            state_value = entry.get("state")
            if not state_value:
                continue
            engagement_state_cards.append(
                {
                    "key": state_value,
                    "label": engagement_state_labels.get(state_value, state_value),
                    "count": entry.get("state_count", entry.get("__count", 0)),
                    "domain": [("state", "=", state_value)],
                }
            )
        engagement_records = engagement_model.search([], order="write_date desc", limit=6)
        engagement_cards = []
        for letter in engagement_records:
            engagement_cards.append(
                {
                    "id": letter.id,
                    "title": letter.name,
                    "client": letter.partner_id.display_name if letter.partner_id else "",
                    "state": engagement_state_labels.get(letter.state, letter.state),
                    "contract_type": letter.contract_type,
                    "url": {"res_model": "bd.engagement.letter", "res_id": letter.id},
                }
            )

        pipeline_records = []
        pipeline_entries = proposal_model.search(pipeline_domain, order="write_date desc", limit=8)
        for record in pipeline_entries:
            pipeline_records.append(
                {
                    "id": record.id,
                    "name": record.name,
                    "client": record.partner_id.display_name or record.client_name or "",
                    "stage": proposal_state_labels.get(record.state, record.state),
                    "amount_display": self._format_currency(record.legal_fees),
                    "date": self._format_date(record.date, lang),
                    "url": {"res_model": "bd.proposal", "res_id": record.id},
                }
            )

        followup_domain = [("state", "in", ("waiting_approval", "approved"))]
        followup_items = []
        followups = proposal_model.search(followup_domain, order="write_date desc", limit=8)
        for record in followups:
            followup_items.append(
                {
                    "id": record.id,
                    "title": record.name,
                    "client": record.partner_id.display_name or record.client_name or "",
                    "stage": proposal_state_labels.get(record.state, record.state),
                    "url": {"res_model": "bd.proposal", "res_id": record.id},
                }
            )

        hero = {
            "clients": clients_total,
            "proposals": proposals_total,
            "approved_proposals": proposals_approved,
            "engagements": engagement_model.search_count([]),
            "documents": documents_total,
            "expiring": expiring_total,
        }

        return {
            "palette": {
                "primary": "#0F5CA8",
                "accent": "#22B6C8",
                "muted": "#0D3E7A",
                "success": "#27AE60",
            },
            "hero": hero,
            "clients": {
                "action": client_action,
                "records": client_cards,
            },
            "proposals": {
                "action": proposal_action,
                "states": proposal_state_cards,
                "records": proposal_records,
                "total": proposals_total,
                "pipeline_amount": self._format_currency(pipeline_amount),
                "open_count": pipeline_count,
            },
            "engagements": {
                "action": engagement_action,
                "states": engagement_state_cards,
                "records": engagement_cards,
            },
            "documents": {
                "action": self._action_payload("qlk_management.action_client_documents"),
                "types": document_types,
                "expiring": expiring_records,
                "domain": expiring_domain,
            },
            "pipeline": {
                "action": proposal_action,
                "records": pipeline_records,
                "domain": pipeline_domain,
            },
            "followups": {
                "action": proposal_action,
                "items": followup_items,
                "domain": followup_domain,
            },
        }
