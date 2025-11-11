# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    client_document_ids = fields.One2many(
        "qlk.client.document",
        "partner_id",
        string="Client Documents",
    )
    document_warning_message = fields.Html(
        string="Document Warning",
        compute="_compute_document_status",
    )
    document_warning_required = fields.Boolean(compute="_compute_document_status")
    doc_company_commercial_register_uploaded = fields.Boolean(compute="_compute_document_status")
    doc_company_trade_license_uploaded = fields.Boolean(compute="_compute_document_status")
    doc_company_poa_uploaded = fields.Boolean(compute="_compute_document_status")
    doc_company_owner_id_uploaded = fields.Boolean(compute="_compute_document_status")
    doc_company_poa_expiration = fields.Date(compute="_compute_document_status")
    doc_individual_id_uploaded = fields.Boolean(compute="_compute_document_status")
    doc_individual_poa_uploaded = fields.Boolean(compute="_compute_document_status")
    doc_individual_poa_expiration = fields.Date(compute="_compute_document_status")

    def _get_required_document_types(self):
        if self.company_type == "company":
            return [
                "company_commercial_register",
                "company_trade_license",
                "company_poa",
                "company_owner_id",
            ]
        return [
            "individual_id",
            "individual_poa",
        ]

    @api.depends(
        "client_document_ids",
        "client_document_ids.attachment_id",
        "client_document_ids.poa_expiration_date",
    )
    def _compute_document_status(self):
        Document = self.env["qlk.client.document"]
        doc_labels = dict(Document.DOC_SELECTION)
        for partner in self:
            doc_map = {doc.doc_type: doc for doc in partner.client_document_ids}
            partner.doc_company_commercial_register_uploaded = bool(
                doc_map.get("company_commercial_register") and doc_map["company_commercial_register"].is_uploaded
            )
            partner.doc_company_trade_license_uploaded = bool(
                doc_map.get("company_trade_license") and doc_map["company_trade_license"].is_uploaded
            )
            company_poa = doc_map.get("company_poa")
            partner.doc_company_poa_uploaded = bool(company_poa and company_poa.is_uploaded)
            partner.doc_company_poa_expiration = company_poa.poa_expiration_date if company_poa else False
            partner.doc_company_owner_id_uploaded = bool(
                doc_map.get("company_owner_id") and doc_map["company_owner_id"].is_uploaded
            )
            individual_id = doc_map.get("individual_id")
            partner.doc_individual_id_uploaded = bool(individual_id and individual_id.is_uploaded)
            individual_poa = doc_map.get("individual_poa")
            partner.doc_individual_poa_uploaded = bool(individual_poa and individual_poa.is_uploaded)
            partner.doc_individual_poa_expiration = individual_poa.poa_expiration_date if individual_poa else False

            missing = []
            for code in partner._get_required_document_types():
                doc = doc_map.get(code)
                if not doc or not doc.is_uploaded:
                    missing.append(doc_labels.get(code, code))
            partner.document_warning_required = bool(missing)
            if missing:
                partner.document_warning_message = "<p class='text-danger'>%s</p>" % (
                    _("Missing documents: %s") % ", ".join(missing)
                )
            else:
                partner.document_warning_message = False

    def get_missing_document_labels(self):
        self.ensure_one()
        Document = self.env["qlk.client.document"]
        doc_labels = dict(Document.DOC_SELECTION)
        doc_map = {doc.doc_type: doc for doc in self.client_document_ids}
        missing = []
        for code in self._get_required_document_types():
            doc = doc_map.get(code)
            if not doc or not doc.is_uploaded:
                missing.append(doc_labels.get(code, code))
        return missing
