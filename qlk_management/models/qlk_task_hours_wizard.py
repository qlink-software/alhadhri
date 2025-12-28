# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class QlkTaskHoursWizard(models.TransientModel):
    _name = "qlk.task.hours.wizard"
    _description = "Hours Logging Wizard"

    name = fields.Char(string="Task Description", required=True)
    hours = fields.Float(string="Hours", required=True)
    date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    user_id = fields.Many2one("res.users", string="User", default=lambda self: self.env.user, required=True)
    proposal_id = fields.Many2one("bd.proposal", string="Proposal")
    engagement_id = fields.Many2one("bd.engagement.letter", string="Engagement Letter")
    partner_id = fields.Many2one("res.partner", string="Contact")
    lead_id = fields.Many2one("crm.lead", string="Opportunity")

    def action_confirm(self):
        self.ensure_one()
        if self.hours <= 0:
            raise UserError(_("Hours must be greater than zero."))

        employee = self.env["hr.employee"].search([("user_id", "=", self.user_id.id)], limit=1)
        if not employee:
            raise UserError(
                _(
                    "لا يوجد موظف مرتبط بالمستخدم الحالي.\n"
                    "No employee is linked to the selected user."
                )
            )

        active_model = self.env.context.get("active_model")
        pending_data = self.env.context.get("pending_data")
        pending_data_list = self.env.context.get("pending_data_list")
        active_ids = self.env.context.get("active_ids") or []
        missing_task_ids = self.env.context.get("missing_task_ids") or active_ids

        def _create_task(record_id):
            task_vals = {
                "name": self.name,
                "description": self.name,
                "hours_spent": self.hours,
                "date_start": self.date,
                "employee_id": employee.id,
                "department": "management",
            }
            if active_model == "bd.proposal":
                task_vals["proposal_id"] = record_id
            elif active_model == "bd.engagement.letter":
                task_vals["engagement_id"] = record_id
            elif active_model == "res.partner":
                task_vals["partner_id"] = record_id
            elif active_model == "crm.lead":
                task_vals["lead_id"] = record_id
            self.env["qlk.task"].create(task_vals)

        Model = self.env[active_model] if active_model else None

        created_records = self.env[active_model].browse() if active_model else self.env["ir.attachment"].browse()

        if pending_data_list and Model:
            created_records = Model.with_context(from_hours_wizard=True).create(pending_data_list)
            for record in created_records:
                _create_task(record.id)
        elif pending_data and Model and not active_ids:
            record = Model.with_context(from_hours_wizard=True).create(pending_data)
            created_records = record
            _create_task(record.id)
        elif pending_data and Model and active_ids:
            Model.with_context(from_hours_wizard=True).browse(active_ids).write(pending_data)
            for rec_id in missing_task_ids:
                _create_task(rec_id)
        elif active_ids:
            for rec_id in missing_task_ids:
                _create_task(rec_id)

        if created_records and len(created_records) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": created_records._name,
                "res_id": created_records.id,
                "view_mode": "form",
                "target": "current",
            }
        return {"type": "ir.actions.client", "tag": "reload"}
