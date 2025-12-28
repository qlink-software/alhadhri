# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class QlkTask(models.Model):
    _inherit = "qlk.task"

    proposal_id = fields.Many2one("bd.proposal", string="Proposal", ondelete="cascade", index=True)
    engagement_id = fields.Many2one(
        "bd.engagement.letter", string="Engagement Letter", ondelete="cascade", index=True
    )
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="cascade", index=True)
    lead_id = fields.Many2one("crm.lead", string="Opportunity", ondelete="cascade", index=True)
    project_id = fields.Many2one("qlk.project", string="Project", ondelete="set null", index=True)

    @api.constrains("department", "case_id", "project_id")
    def _check_litigation_links(self):
        for task in self:
            if task.department != "litigation":
                continue
            if not task.case_id and not task.project_id:
                raise ValidationError(
                    _(
                        "يجب ربط مهام التقاضي بقضية أو مشروع تقاضي.\n"
                        "Litigation tasks must be linked to a litigation case or litigation project."
                    )
                )
