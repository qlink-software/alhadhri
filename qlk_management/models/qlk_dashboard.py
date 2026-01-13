# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديول لوحة تحكم BD
# هذا الملف يوفر بيانات الداشبورد بما في ذلك الإحصائيات، التنبيهات،
# حالة العروض، اتفاقيات الارتباط، الوثائق، والفرص في الـ CRM.
# ------------------------------------------------------------------------------
from odoo import _, api, fields, models
from odoo.tools.misc import format_date


class ManagementDashboard(models.AbstractModel):
    _name = "qlk.management.dashboard"
    _description = "Management Dashboard Service"

    # ------------------------------------------------------------------------------
    # دالة مساعدة لاسترجاع تعريف أي أكشن عبر XML-ID لاستخدامه في الواجهة.
    # ------------------------------------------------------------------------------
    def _action_payload(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        if action:
            return {"id": action.id}
        return None

    # ------------------------------------------------------------------------------
    # تنسيق التاريخ حسب لغة المستخدم الحالية لضمان مخرجات موحدة.
    # ------------------------------------------------------------------------------
    def _format_date(self, date_value, lang):
        if not date_value:
            return ""
        return format_date(self.env, date_value, lang_code=lang)

    # ------------------------------------------------------------------------------
    # تحديد حالة الترجمة بناءً على حالة الترجمة في المستند.
    # ------------------------------------------------------------------------------
    def _translation_status(self, needs_translation, is_translated):
        if not needs_translation:
            return {"label": _("No translation"), "css": "chip-muted"}
        if is_translated:
            return {"label": _("Translated"), "css": "chip-success"}
        return {"label": _("Pending"), "css": "chip-danger"}

    @api.model
    def get_dashboard_data(self):
        lang = self.env.user.lang or "en_US"

        proposal_model = self.env.get("bd.proposal")
        engagement_model = self.env.get("bd.engagement.letter")
        partner_model = self.env["res.partner"]
        document_model = self.env.get("qlk.client.document")
        crm_model = self.env.get("crm.lead")

        proposals_total = proposals_waiting = proposals_approved = legal_total = collected_total = pending_total = 0.0
        proposals_action = self._action_payload("qlk_management.action_bd_proposal")
        if proposal_model:
            proposals_total = proposal_model.search_count([])
            proposals_waiting = proposal_model.search_count(
                [("state", "in", ("waiting_manager_approval", "waiting_client_approval"))]
            )
            proposals_approved = proposal_model.search_count([("state", "=", "approved_client")])
            if proposal_amount_group:
                legal_total = proposal_amount_group[0].get("legal_fees") or 0.0

        proposal_reports = [
            {"label": _("Total Proposals"), "action": self._action_payload("qlk_management.action_bd_proposal_report_total")},
            {"label": _("Amount Collected"), "action": self._action_payload("qlk_management.action_bd_proposal_report_collected")},
            {"label": _("Proposals by Status"), "action": self._action_payload("qlk_management.action_bd_proposal_report_status")},
        ]

        engagement_total = engagement_waiting = 0
        engagement_action = self._action_payload("qlk_management.action_bd_engagement_letter")
        engagement_types = []
        if engagement_model:
            engagement_total = engagement_model.search_count([])
            engagement_waiting = engagement_model.search_count(
                [("state", "in", ("waiting_manager_approval", "waiting_client_approval"))]
            )
            engagement_type_groups = engagement_model.read_group(
                [], ["retainer_type"], ["retainer_type"]
            )
            engagement_types = [
                {
                    "type": data["retainer_type"],
                    "count": data["retainer_type_count"],
                }
                for data in engagement_type_groups
                if data.get("retainer_type")
            ]

        client_domain = [("customer_rank", ">", 0)]
        clients_total = partner_model.search_count(client_domain)
        clients_action = self._action_payload("qlk_management.action_bd_client_data")

        documents_total = 0
        translation_pending = []
        clients_with_docs = 0
        poa_documents_action = None
        if document_model:
            poa_documents_action = self._action_payload("qlk_management.action_client_documents")
            documents_total = document_model.search_count([])
            doc_labels = dict(document_model._fields["document_type"].selection)
            pending_docs = document_model.search(
                [("needs_translation", "=", True), ("is_translated", "=", False)],
                order="create_date desc",
                limit=10,
            )
            for doc in pending_docs:
                status = self._translation_status(doc.needs_translation, doc.is_translated)
                created_on = fields.Datetime.to_date(doc.create_date) if doc.create_date else False
                translation_pending.append(
                    {
                        "id": doc.id,
                        "partner": doc.partner_id.display_name if doc.partner_id else "",
                        "doc_type": doc_labels.get(doc.document_type, doc.document_type),
                        "expires_on": self._format_date(created_on, lang),
                        "status": status["label"],
                        "status_class": status["css"],
                        "url": {"res_model": "qlk.client.document", "res_id": doc.id},
                    }
                )
            partners_with_docs = document_model.read_group([], ["partner_id"], ["partner_id"])
            clients_with_docs = len(partners_with_docs)

        pipeline_total = pipeline_open = pipeline_won = 0
        pipeline_action = self._action_payload("crm.crm_lead_action_pipeline")
        pipeline_stages = []
        if crm_model:
            pipeline_domain = [("type", "=", "opportunity"), ("active", "=", True)]
            pipeline_total = crm_model.search_count(pipeline_domain)
            pipeline_open = crm_model.search_count(pipeline_domain + [("probability", "<", 100)])
            pipeline_won = crm_model.search_count(pipeline_domain + [("probability", "=", 100)])
            stage_stats = crm_model.read_group(pipeline_domain, ["stage_id"], ["stage_id"])
            pipeline_stages = [
                {"stage": data["stage_id"][1], "count": data["stage_id_count"]}
                for data in stage_stats
                if data.get("stage_id")
            ]

        return {
            "palette": {
                "primary": "#0c2d48",
                "accent": "#7fa2c3",
                "muted": "#091a2c",
                "success": "#2EA091",
            },
            "hero": {
                "clients": clients_total,
                "proposals": proposals_total,
                "approved_proposals": proposals_approved,
                "engagements": engagement_total,
                "documents": documents_total,
            },
            "proposals": {
                "total": proposals_total,
                "approved": proposals_approved,
                "waiting": proposals_waiting,
                "billable": legal_total,
                "collected": collected_total,
                "pending": pending_total,
                "action": proposals_action,
                "reports": proposal_reports,
            },
            "engagements": {
                "total": engagement_total,
                "waiting": engagement_waiting,
                "types": engagement_types,
                "action": engagement_action,
            },
            "clients": {
                "total": clients_total,
                "with_documents": clients_with_docs,
                "documents_total": documents_total,
                "action": clients_action,
                "documents_action": poa_documents_action,
            },
            "alerts": {
                "expiring": translation_pending,
            },
            "pipeline": {
                "total": pipeline_total,
                "open": pipeline_open,
                "won": pipeline_won,
                "action": pipeline_action,
                "stages": pipeline_stages,
            },
        }
