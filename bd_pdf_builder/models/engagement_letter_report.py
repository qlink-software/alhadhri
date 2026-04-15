# -*- coding: utf-8 -*-
from odoo import models


class BdEngagementLetter(models.Model):
    _inherit = "bd.engagement.letter"

    def _get_or_create_engagement_report_action(self):
        xmlid = "bd_pdf_builder.action_engagement_letter_pdf"
        paperformat = self.env.ref("bd_pdf_builder.paperformat_engagement_letter_pdf", raise_if_not_found=False)
        report_name = "bd_pdf_builder.report_engagement_letter_pdf"
        print_name_expr = "'Engagement Letter - %s' % (object.display_name or object.id)"

        desired_vals = {
            "name": "Engagement Letter PDF",
            "model": "bd.engagement.letter",
            "report_type": "qweb-pdf",
            "report_name": report_name,
            "report_file": report_name,
            "print_report_name": print_name_expr,
        }
        if paperformat:
            desired_vals["paperformat_id"] = paperformat.id

        action = self.env.ref(xmlid, raise_if_not_found=False)
        if action:
            updates = {}
            for key, value in desired_vals.items():
                current = action[key]
                current_value = current.id if key == "paperformat_id" else current
                if current_value != value:
                    updates[key] = value
            if updates:
                action.sudo().write(updates)
            return action

        report_model = self.env["ir.actions.report"].sudo()
        action = report_model.search(
            [
                ("report_name", "=", report_name),
                ("model", "=", "bd.engagement.letter"),
            ],
            limit=1,
        )
        if action:
            updates = {k: v for k, v in desired_vals.items() if action[k] != v}
            if updates:
                action.write(updates)
        else:
            action = report_model.create(desired_vals)

        imd = self.env["ir.model.data"].sudo()
        if not imd.search(
            [("module", "=", "bd_pdf_builder"), ("name", "=", "action_engagement_letter_pdf")],
            limit=1,
        ):
            imd.create(
                {
                    "module": "bd_pdf_builder",
                    "name": "action_engagement_letter_pdf",
                    "model": "ir.actions.report",
                    "res_id": action.id,
                    "noupdate": True,
                }
            )

        return action

    def action_print_engagement_pdf(self):
        self.ensure_one()
        action = self._get_or_create_engagement_report_action()
        return action.report_action(self)
