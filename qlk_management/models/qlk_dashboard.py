# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديول لوحة تحكم BD
# هذا الملف يوفر بيانات الداشبورد بما في ذلك الإحصائيات، التنبيهات،
# حالة العروض، اتفاقيات الارتباط، الوثائق، والفرص في الـ CRM.
# ------------------------------------------------------------------------------
from odoo import _, api, fields, models
from odoo.osv.expression import OR
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

    # ------------------------------------------------------------------------------
    # هذه الدالة تبني دومين بيانات مرتبط بالمستخدم الحالي عند الحاجة.
    # ------------------------------------------------------------------------------
    def _scoped_domain(self, model_name, user, employee_ids, allow_all, base_domain=None):
        domain = list(base_domain or [])
        if allow_all or model_name not in self.env:
            return domain

        Model = self.env[model_name]
        user_scopes = []
        if "reviewer_id" in Model._fields:
            user_scopes.append([("reviewer_id", "=", user.id)])
        if "user_id" in Model._fields:
            user_scopes.append([("user_id", "=", user.id)])
        if "owner_id" in Model._fields:
            user_scopes.append([("owner_id", "=", user.id)])
        if "assigned_user_id" in Model._fields:
            user_scopes.append([("assigned_user_id", "=", user.id)])
        if employee_ids and "employee_id" in Model._fields:
            user_scopes.append([("employee_id", "in", employee_ids)])
        if employee_ids and "assigned_employee_ids" in Model._fields:
            user_scopes.append([("assigned_employee_ids", "in", employee_ids)])
        if "create_uid" in Model._fields:
            user_scopes.append([("create_uid", "=", user.id)])

        if user_scopes:
            domain += OR(user_scopes)
        return domain

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        employee_ids = user.employee_ids.ids
        lang = user.lang or "en_US"
        # هذا المتغير يفعل الرؤية الشاملة للمديرين فقط.
        allow_all = user._qlk_can_view_all_dashboards()

        proposal_model = self.env.get("bd.proposal")
        engagement_model = self.env.get("bd.engagement.letter")
        partner_model = self.env["res.partner"]
        document_model = self.env.get("qlk.client.document")
        crm_model = self.env.get("crm.lead")

        proposal_domain = self._scoped_domain("bd.proposal", user, employee_ids, allow_all)
        engagement_domain = self._scoped_domain("bd.engagement.letter", user, employee_ids, allow_all)

        proposals_total = proposals_waiting = proposals_approved = legal_total = collected_total = pending_total = 0.0
        proposals_action = self._action_payload("qlk_management.action_bd_proposal")
        if proposal_model:
            proposals_total = proposal_model.search_count(proposal_domain)
            proposals_waiting = proposal_model.search_count(
                proposal_domain + [("state", "in", ("waiting_manager_approval", "waiting_client_approval"))]
            )
            proposals_approved = proposal_model.search_count(proposal_domain + [("state", "=", "approved_client")])
            proposal_amount_group = proposal_model.read_group(proposal_domain, ["legal_fees"], [])
            if proposal_amount_group:
                legal_total = proposal_amount_group[0].get("legal_fees") or 0.0

            if "payment_status" in proposal_model._fields and "total_amount" in proposal_model._fields:
                collected_group = proposal_model.read_group(
                    proposal_domain + [("payment_status", "=", "paid")],
                    ["total_amount"],
                    [],
                )
                pending_group = proposal_model.read_group(
                    proposal_domain + [("payment_status", "in", ("unpaid", "partial"))],
                    ["total_amount"],
                    [],
                )
                collected_total = (collected_group and collected_group[0].get("total_amount") or 0.0) or 0.0
                pending_total = (pending_group and pending_group[0].get("total_amount") or 0.0) or 0.0

        proposal_reports = [
            {"label": _("Total Proposals"), "action": self._action_payload("qlk_management.action_bd_proposal_report_total")},
            {"label": _("Amount Collected"), "action": self._action_payload("qlk_management.action_bd_proposal_report_collected")},
            {"label": _("Proposals by Status"), "action": self._action_payload("qlk_management.action_bd_proposal_report_status")},
        ]

        engagement_total = engagement_waiting = 0
        engagement_action = self._action_payload("qlk_management.action_bd_engagement_letter")
        engagement_types = []
        if engagement_model:
            engagement_total = engagement_model.search_count(engagement_domain)
            engagement_waiting = engagement_model.search_count(
                engagement_domain + [("state", "in", ("waiting_manager_approval", "waiting_client_approval"))]
            )
            engagement_type_groups = engagement_model.read_group(
                engagement_domain,
                ["retainer_type"],
                ["retainer_type"],
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
        if not allow_all:
            # هذه الخطوة تربط قائمة العملاء بملفات المستخدم الفعلية فقط.
            partner_ids = set()
            if proposal_model:
                partner_ids.update(proposal_model.search(proposal_domain).mapped("partner_id").ids)
            if engagement_model:
                partner_ids.update(engagement_model.search(engagement_domain).mapped("partner_id").ids)
            client_domain.append(("id", "in", list(partner_ids or {0})))

        clients_total = partner_model.search_count(client_domain)
        clients_action = self._action_payload("qlk_management.action_bd_client_data")

        documents_total = 0
        translation_pending = []
        clients_with_docs = 0
        poa_documents_action = None
        if document_model:
            poa_documents_action = self._action_payload("qlk_management.action_client_documents")
            document_domain = []
            if not allow_all:
                client_ids = partner_model.search(client_domain).ids
                document_domain = [("partner_id", "in", client_ids or [0])]

            documents_total = document_model.search_count(document_domain)
            doc_labels = dict(document_model._fields["document_type"].selection)
            pending_docs = document_model.search(
                document_domain + [("needs_translation", "=", True), ("is_translated", "=", False)],
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
            partners_with_docs = document_model.read_group(document_domain, ["partner_id"], ["partner_id"])
            clients_with_docs = len(partners_with_docs)

        pipeline_total = pipeline_open = pipeline_won = 0
        pipeline_action = self._action_payload("crm.crm_lead_action_pipeline")
        pipeline_stages = []
        if crm_model:
            pipeline_domain = [("type", "=", "opportunity"), ("active", "=", True)]
            if not allow_all and "user_id" in crm_model._fields:
                pipeline_domain.append(("user_id", "=", user.id))

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
