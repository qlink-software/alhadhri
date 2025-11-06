# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EngagementSequence(models.Model):
    _name = "qlk.engagement.sequence"
    _description = "Engagement Reference Sequence"
    _order = "sequence_type, year desc"
    _rec_name = "display_name"

    sequence_type = fields.Selection(
        selection=[
            ("L", "Litigation"),
            ("C", "Corporate"),
            ("CL", "Combined"),
            ("A", "Arbitration"),
        ],
        required=True,
        string="Department",
    )
    year = fields.Integer(
        string="Year",
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    prefix = fields.Char(string="Prefix", default="AH/EL/", required=True)
    last_number = fields.Integer(string="Last Number", default=0, required=True)
    next_number = fields.Char(
        string="Next Reference",
        compute="_compute_next_number",
        store=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    display_name = fields.Char(compute="_compute_display_name", store=False)

    _sql_constraints = [
        (
            "sequence_unique_per_year",
            "unique(sequence_type, year, company_id)",
            "Each company can only have one engagement sequence per department and year.",
        ),
    ]

    def _compute_display_name(self):
        for record in self:
            record.display_name = "%s%s/%s" % (
                record.prefix or "",
                record.sequence_type or "",
                record.year or "",
            )

    @api.depends("prefix", "sequence_type", "last_number", "year")
    def _compute_next_number(self):
        for record in self:
            next_counter = (record.last_number or 0) + 1
            record.next_number = "%s%s/%03d/%s" % (
                record.prefix or "",
                record.sequence_type or "",
                next_counter,
                record.year or datetime.now().year,
            )

    @api.constrains("last_number")
    def _check_last_number(self):
        for record in self:
            if record.last_number < 0:
                raise ValidationError(_("Last number must be positive."))

    @api.model
    def _next_reference(self, department_code, company):
        year = fields.Date.context_today(self).year
        sequence = self.search(
            [
                ("sequence_type", "=", department_code),
                ("year", "=", year),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if not sequence:
            sequence = self.create(
                {
                    "sequence_type": department_code,
                    "year": year,
                    "company_id": company.id,
                }
            )
        sequence.write({"last_number": sequence.last_number + 1})
        serial = sequence.last_number
        reference = "%s%s/%03d/%s" % (sequence.prefix, department_code, serial, sequence.year)
        return reference, serial, sequence.year
