# -*- coding: utf-8 -*-
from odoo import api, fields, models


class QlkProjectStage(models.Model):
    _name = "qlk.project.stage"
    _description = "Project Stage"
    _order = "stage_type, sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    stage_type = fields.Selection(
        selection=[
            ("pre_litigation", "Pre-Litigation"),
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
        ],
        required=True,
        default="pre_litigation",
    )
    technical_code = fields.Char(help="Technical identifier used for automation rules.")
    stage_code = fields.Char(string="Stage Code", help="Short code used when generating project numbers.")
    stage_number = fields.Integer(
        string="Stage Number",
        help="Applied to litigation project codes (e.g. Appeal = 1, Cassation = 2). Leave empty for first instance.",
    )
    description = fields.Text()
    is_default = fields.Boolean(
        string="Default Stage",
        help="Set this stage as the starting point for the related project type.",
    )
    auto_task_template = fields.Boolean(
        string="Auto Task Required",
        help="Automatically create a subtask when the project reaches this stage.",
    )
    auto_task_name = fields.Char(string="Auto Task Name")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)


class QlkCaseStageLog(models.Model):
    _name = "qlk.case.stage.log"
    _description = "Case Stage Log"
    _order = "id desc"

    case_id = fields.Many2one("qlk.case", required=True, ondelete="cascade")
    stage_id = fields.Many2one("qlk.project.stage", required=True, ondelete="restrict")
    date_start = fields.Datetime(default=fields.Datetime.now, required=True)
    date_end = fields.Datetime()
    duration_days = fields.Float(compute="_compute_duration", store=True)
    completed_by = fields.Many2one("res.users")

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for record in self:
            end = record.date_end or fields.Datetime.now()
            if record.date_start:
                delta = end - record.date_start
                record.duration_days = delta.total_seconds() / 86400.0
            else:
                record.duration_days = 0.0
