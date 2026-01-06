# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

COMPLETION_SECTIONS = {
    "completion_identification": [
        "case_number",
        "case_year",
        "folder_number",
        "folder_year",
        "case_group",
        "main_category",
        "second_category",
        "building",
    ],
    "completion_timeline": [
        "date",
        "receiving_date",
        "case_value",
        "employee_id",
        "employee_ids",
    ],
    "completion_parties": [
        "client_id",
        "client_desc",
        "client_ids",
        "client_descs",
        "opponent_id",
        "opponent_desc",
        "opponent_ids",
        "opponents_desc",
    ],
    "completion_details": [
        "subject",
        "description",
        "linked_case",
        "linked_cases",
        "related_case",
    ],
    "completion_documents": [
        # "client_document_ids",
        "attachment_ids",
    ],
}

COMPLETION_DEPENDS = sorted({field for values in COMPLETION_SECTIONS.values() for field in values})


class QlkCase(models.Model):
    _inherit = "qlk.case"

    litigation_flow = fields.Selection(
        selection=[
            ("pre_litigation", "Pre-Litigation"),
            ("litigation", "Litigation"),
        ],
        string="Proceeding Type",
        default="pre_litigation",
        required=True,
        tracking=True,
    )
    client_capacity = fields.Char(string="Client Capacity/Title")
    # client_document_ids = fields.One2many(
    #     related="client_id.client_document_ids",
    #     string="Client Documents",
    #     readonly=True,
    # )
    pre_litigation_id = fields.Many2one(
        "qlk.pre.litigation",
        string="Pre-Litigation Workflow",
        tracking=True,
    )
    completion_identification = fields.Float(string="Identification", compute="_compute_completion_metrics", store=False)
    completion_timeline = fields.Float(string="Timeline", compute="_compute_completion_metrics", store=False)
    completion_parties = fields.Float(string="Parties", compute="_compute_completion_metrics", store=False)
    completion_details = fields.Float(string="Details", compute="_compute_completion_metrics", store=False)
    completion_documents = fields.Float(string="Documents", compute="_compute_completion_metrics", store=False)
    completion_overall = fields.Float(string="Overall Completion", compute="_compute_completion_metrics", store=False)


    @api.depends(*COMPLETION_DEPENDS)
    def _compute_completion_metrics(self):
        sections = COMPLETION_SECTIONS
        section_keys = sections.keys()
        for record in self:
            metrics = {}
            for key, field_names in sections.items():
                total = len(field_names)
                if not total:
                    metrics[key] = 0.0
                    continue
                filled = sum(
                    1 for field_name in field_names if record._is_field_value_filled(field_name)
                )
                metrics[key] = round((filled / total) * 100.0, 2)

            record.completion_identification = metrics.get("completion_identification", 0.0)
            record.completion_timeline = metrics.get("completion_timeline", 0.0)
            record.completion_parties = metrics.get("completion_parties", 0.0)
            record.completion_details = metrics.get("completion_details", 0.0)
            record.completion_documents = metrics.get("completion_documents", 0.0)
            if section_keys:
                record.completion_overall = round(
                    sum(metrics.get(key, 0.0) for key in section_keys) / len(section_keys), 2
                )
            else:
                record.completion_overall = 0.0

    def _is_field_value_filled(self, field_name):
        if field_name not in self._fields:
            return False
        value = self[field_name]
        if isinstance(value, models.BaseModel):
            return bool(value)
        if isinstance(value, (list, tuple, set)):
            return bool(value)
        if isinstance(value, (int, float)):
            return value not in (False, 0, 0.0)
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)

    def _get_case_notification_partners(self):
        partners = self.env["res.partner"]
        employees = self.employee_id
        if hasattr(self, "employee_ids"):
            employees |= self.employee_ids
        partners |= employees.mapped("user_id.partner_id")
        return partners

    def _notify_case_event(self, message):
        partners = self._get_case_notification_partners()
        if partners:
            self.message_subscribe(partner_ids=partners.ids, subtype_ids=None)
            self.message_post(body=message, partner_ids=partners.ids)
        else:
            self.message_post(body=message)
