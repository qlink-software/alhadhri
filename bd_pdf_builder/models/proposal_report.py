# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class BdProposal(models.Model):
    _inherit = "bd.proposal"

    def _get_report_image_attachments(self):
        self.ensure_one()
        attachment_model = self.env["ir.attachment"].sudo()
        report_attachments = attachment_model.search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            order="id",
        )
        attachments = (self.client_attachment_ids | report_attachments).sorted(lambda att: att.id)

        unique_attachments = attachment_model.browse()
        seen = set()
        for attachment in attachments:
            if not attachment.datas:
                continue
            if not (attachment.mimetype or "").startswith("image/"):
                continue
            key = attachment.checksum or (attachment.name, attachment.file_size, attachment.mimetype)
            if key in seen:
                continue
            seen.add(key)
            unique_attachments |= attachment
        return unique_attachments

    def action_print_proposal(self):
        for proposal in self:
            if proposal.state != "approved_client":
                raise UserError(_("Printing is available only after approval."))
        return self.env.ref("bd_pdf_builder.action_proposal_pdf").report_action(self)
