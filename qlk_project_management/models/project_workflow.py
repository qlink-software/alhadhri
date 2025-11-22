# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# نموذج خطوط مراحل المشروع (Workflow Stages) لتمثيل مراحل التقاضي داخل
# الواجهات مع حقول التاريخ والتقدم والملاحظات والمرفقات.
# ------------------------------------------------------------------------------
from odoo import fields, models


class QlkProjectStageLine(models.Model):
    _name = "qlk.project.stage.line"
    _description = "Project Workflow Stage"
    _order = "project_id, sequence, id"

    project_id = fields.Many2one("qlk.project", string="Project", required=True, ondelete="cascade")
    name = fields.Char(string="Stage Name", required=True)
    stage_key = fields.Char(string="Technical Key", help="Unique key used to avoid creating duplicate stage lines.")
    sequence = fields.Integer(default=10)
    due_date = fields.Date(string="Due Date")
    progress = fields.Float(string="Progress %", digits=(6, 2), default=0.0)
    comment = fields.Text(string="Comments / Updates")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_project_stage_line_attachment_rel",
        "stage_line_id",
        "attachment_id",
        string="Attachments",
    )
    task_id = fields.Many2one("qlk.task", string="Linked Task")
