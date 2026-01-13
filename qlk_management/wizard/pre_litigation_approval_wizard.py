# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PreLitigationApprovalWizard(models.TransientModel):
    _name = "qlk.pre.litigation.approval.wizard"
    _description = "Pre-Litigation Approval Wizard"

    pre_litigation_id = fields.Many2one("qlk.pre.litigation", string="Pre-Litigation", required=True)
    line_ids = fields.One2many(
        "qlk.pre.litigation.approval.wizard.line",
        "wizard_id",
        string="Approvals",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        pre_litigation_id = self.env.context.get("default_pre_litigation_id")
        if not pre_litigation_id:
            return res
        pre_litigation = self.env["qlk.pre.litigation"].browse(pre_litigation_id)
        res["pre_litigation_id"] = pre_litigation_id
        res["line_ids"] = [
            (0, 0, {"user_id": line.user_id.id, "sequence": line.sequence})
            for line in pre_litigation.approval_line_ids.sorted("sequence")
        ]
        return res

    def action_save_draft(self):
        self._apply_lines(submit=False)
        return {"type": "ir.actions.act_window_close"}

    def action_submit(self):
        self._apply_lines(submit=True)
        return {"type": "ir.actions.act_window_close"}

    def _apply_lines(self, submit):
        self.ensure_one()
        self._ensure_editable()
        line_vals = [
            (0, 0, {"user_id": line.user_id.id, "sequence": line.sequence, "state": "pending"})
            for line in self.line_ids
        ]
        self.pre_litigation_id.write(
            {
                "approval_line_ids": [(5, 0, 0)] + line_vals,
                "approvals_submitted": bool(submit),
            }
        )
        if not submit:
            self.pre_litigation_id.approval_line_ids.write({"approval_date": False, "state": "pending"})

    def _ensure_editable(self):
        self.ensure_one()
        pre_litigation = self.pre_litigation_id
        if pre_litigation.approvals_submitted and not pre_litigation.approvals_completed and not pre_litigation.approvals_rejected:
            raise UserError(_("Approvals are already submitted and cannot be edited."))


class PreLitigationApprovalWizardLine(models.TransientModel):
    _name = "qlk.pre.litigation.approval.wizard.line"
    _description = "Pre-Litigation Approval Wizard Line"

    wizard_id = fields.Many2one(
        "qlk.pre.litigation.approval.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one("res.users", string="Approver", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
