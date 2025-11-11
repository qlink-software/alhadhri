# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class QlkAppeal(models.Model):
    _inherit = "qlk.appeal"

    allowed_case_type_ids = fields.Many2many(
        "qlk.secondcategory",
        "qlk_appeal_case_type_rel",
        "appeal_id",
        "case_type_id",
        string="Allowed Case Types",
    )


class QlkAppealDate(models.Model):
    _inherit = "qlk.appealdate"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            message = _("Appeal deadline %s has been logged.") % (
                fields.Datetime.to_string(record.last_appeal_date)
                if record.last_appeal_date
                else record.appeals_date.display_name
            )
            for case in record.case_ids:
                case._notify_case_event(message)
        return records

    @api.onchange("case_ids")
    def _onchange_case_ids(self):
        if not self.case_ids:
            return {"domain": {"appeals_date": []}}
        case_types = self.case_ids.mapped("second_category").ids
        if case_types:
            domain = [
                "|",
                ("allowed_case_type_ids", "=", False),
                ("allowed_case_type_ids", "in", case_types),
            ]
        else:
            domain = [("allowed_case_type_ids", "=", False)]
        return {"domain": {"appeals_date": domain}}


class QlkRequest(models.Model):
    _inherit = "qlk.request"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.case_id:
                message = _("New request %(subject)s scheduled for %(date)s.") % {
                    "subject": record.subject or record.name,
                    "date": record.request_date or record.date,
                }
                record.case_id._notify_case_event(message)
        return records


class QlkImplementationProcedure(models.Model):
    _inherit = "qlk.implementation.procedure"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.case_id:
                message = _("Implementation procedure %(name)s has been created.") % {
                    "name": record.name,
                }
                record.case_id._notify_case_event(message)
        return records


class QlkConsulting(models.Model):
    _inherit = "qlk.consulting"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            partners = record.employee_id.user_id.partner_id
            if partners:
                record.message_subscribe(partner_ids=partners.ids, subtype_ids=None)
                record.message_post(
                    body=_("Consultation %s has been created.") % record.name,
                    partner_ids=partners.ids,
                )
        return records


class QlkCorporateCase(models.Model):
    _inherit = "qlk.corporate.case"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._notify_responsible_user(_("Corporate case %s created.") % record.name)
        return records

    def write(self, vals):
        result = super().write(vals)
        if "responsible_employee_id" in vals:
            for record in self:
                record._notify_responsible_user(
                    _("You have been assigned to corporate case %s.") % record.name
                )
        return result

    def _notify_responsible_user(self, message):
        partner = self.responsible_employee_id.user_id.partner_id
        if partner:
            self.message_subscribe(partner_ids=partner.ids, subtype_ids=None)
            self.message_post(body=message, partner_ids=partner.ids)


class QlkArbitrationCase(models.Model):
    _inherit = "qlk.arbitration.case"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._notify_responsible_user(_("Arbitration case %s created.") % record.name)
        return records

    def write(self, vals):
        result = super().write(vals)
        if "responsible_employee_id" in vals:
            for record in self:
                record._notify_responsible_user(
                    _("You have been assigned to arbitration case %s.") % record.name
                )
        return result

    def _notify_responsible_user(self, message):
        partner = self.responsible_employee_id.user_id.partner_id
        if partner:
            self.message_subscribe(partner_ids=partner.ids, subtype_ids=None)
            self.message_post(body=message, partner_ids=partner.ids)
