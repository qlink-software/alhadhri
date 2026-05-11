# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class QlkPoaUploadWizard(models.TransientModel):
    _name = "qlk.poa.upload.wizard"
    _description = "Upload Power of Attorney"

    client_file_id = fields.Many2one("qlk.client.file", string="Client File", required=True, readonly=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_poa_upload_wizard_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Signed POA",
        required=True,
    )
    poa_received_date = fields.Date(string="Received Date", default=fields.Date.context_today, required=True)
    poa_expiry_date = fields.Date(string="Expiry Date")
    poa_notes = fields.Text(string="Notes")

    def action_upload(self):
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_("Upload at least one signed POA attachment."))
        client_file = self.client_file_id
        client_file._check_poa_manager()
        for attachment in self.attachment_ids:
            attachment.sudo().write({"res_model": client_file._name, "res_id": client_file.id})

        notes = client_file.poa_notes or ""
        if self.poa_notes:
            notes = (notes + "\n" if notes else "") + self.poa_notes

        client_file.write(
            {
                "poa_attachment_ids": [(4, attachment_id) for attachment_id in self.attachment_ids.ids],
                "poa_status": "uploaded",
                "poa_received_date": self.poa_received_date,
                "poa_expiry_date": self.poa_expiry_date or client_file.poa_expiry_date,
                "poa_notes": notes,
                "poa_uploaded_by": self.env.user.id,
            }
        )
        client_file._propagate_poa_attachments()
        client_file.message_post(
            body=_("Signed POA has been uploaded."),
            attachment_ids=self.attachment_ids.ids,
        )
        return {"type": "ir.actions.act_window_close"}
