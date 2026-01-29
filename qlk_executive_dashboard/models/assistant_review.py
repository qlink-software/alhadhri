# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BDProposalAssistantReview(models.Model):
    _inherit = "bd.proposal"

    assistant_recommendation = fields.Selection(
        selection=[
            ("recommend", "Recommended"),
            ("revision", "Needs Revision"),
        ],
        string="Assistant Recommendation",
        tracking=True,
    )
    assistant_note = fields.Text(string="Assistant Note", tracking=True)
    assistant_reviewed_on = fields.Datetime(string="Reviewed On", tracking=True)
    assistant_reviewer_id = fields.Many2one("res.users", string="Reviewed By", tracking=True)

    def action_set_assistant_recommendation(self, recommendation, note=""):
        if recommendation not in {"recommend", "revision"}:
            raise UserError(_("Invalid recommendation action."))
        for record in self:
            record._ensure_state({"waiting_manager_approval"})
            if recommendation == "revision" and not (note or "").strip():
                raise UserError(_("Please provide the revision reason."))
            record.write(
                {
                    "assistant_recommendation": recommendation,
                    "assistant_note": note,
                    "assistant_reviewed_on": fields.Datetime.now(),
                    "assistant_reviewer_id": self.env.user.id,
                }
            )
            message = _("Assistant recommendation: %s") % (
                "Recommended" if recommendation == "recommend" else "Needs Revision"
            )
            if note:
                message = f"{message}<br/>{note}"
            record.message_post(body=message)


class BDEngagementAssistantReview(models.Model):
    _inherit = "bd.engagement.letter"

    assistant_recommendation = fields.Selection(
        selection=[
            ("recommend", "Recommended"),
            ("revision", "Needs Revision"),
        ],
        string="Assistant Recommendation",
        tracking=True,
    )
    assistant_note = fields.Text(string="Assistant Note", tracking=True)
    assistant_reviewed_on = fields.Datetime(string="Reviewed On", tracking=True)
    assistant_reviewer_id = fields.Many2one("res.users", string="Reviewed By", tracking=True)

    def action_set_assistant_recommendation(self, recommendation, note=""):
        if recommendation not in {"recommend", "revision"}:
            raise UserError(_("Invalid recommendation action."))
        for record in self:
            record._ensure_state({"waiting_manager_approval"})
            if recommendation == "revision" and not (note or "").strip():
                raise UserError(_("Please provide the revision reason."))
            record.write(
                {
                    "assistant_recommendation": recommendation,
                    "assistant_note": note,
                    "assistant_reviewed_on": fields.Datetime.now(),
                    "assistant_reviewer_id": self.env.user.id,
                }
            )
            message = _("Assistant recommendation: %s") % (
                "Recommended" if recommendation == "recommend" else "Needs Revision"
            )
            if note:
                message = f"{message}<br/>{note}"
            record.message_post(body=message)
