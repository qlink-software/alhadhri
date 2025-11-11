# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class QlkClientDocument(models.Model):
    _name = "qlk.client.document"
    _description = "Client Document"
    _order = "partner_id, doc_type"

    DOC_SELECTION = [
        ("company_commercial_register", "Commercial Registration"),
        ("company_trade_license", "Trade License"),
        ("company_poa", "Company Power of Attorney"),
        ("company_owner_id", "Owner ID Copy"),
        ("individual_id", "Personal ID"),
        ("individual_poa", "Personal Power of Attorney"),
    ]

    partner_id = fields.Many2one("res.partner", string="Client", required=True, ondelete="cascade", index=True)
    doc_type = fields.Selection(selection=DOC_SELECTION, required=True, string="Document Type", index=True)
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Attachment",
        ondelete="set null",
        help="Upload or link the supporting document.",
    )
    is_uploaded = fields.Boolean(string="Uploaded", compute="_compute_is_uploaded", store=True)
    poa_expiration_date = fields.Date(string="POA Expiration")
    poa_reference = fields.Char(string="POA Reference / Number")
    note = fields.Text(string="Notes")

    _sql_constraints = [
        ("partner_doc_unique", "unique(partner_id, doc_type)", "Each document type can only be added once per client."),
    ]

    @api.depends("attachment_id")
    def _compute_is_uploaded(self):
        for record in self:
            record.is_uploaded = bool(record.attachment_id)

    def name_get(self):
        result = []
        doc_labels = dict(self.DOC_SELECTION)
        for record in self:
            label = doc_labels.get(record.doc_type, record.doc_type or "")
            if record.partner_id:
                label = f"{record.partner_id.display_name} - {label}"
            result.append((record.id, label))
        return result
