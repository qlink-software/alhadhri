# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from .litigation_level import LITIGATION_STAGE_CODE_SELECTION

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
    project_id = fields.Many2one(
        "qlk.project",
        string="المشروع",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    project_sequence = fields.Char(
        string="رقم المشروع",
        compute="_compute_project_sequence",
        store=True,
        readonly=True,
    )
    litigation_level_id = fields.Many2one(
        "litigation.level",
        string="درجة التقاضي",
        tracking=True,
        index=True,
    )
    litigation_stage_code = fields.Selection(
        selection=LITIGATION_STAGE_CODE_SELECTION,
        string="Stage Code",
        related="litigation_level_id.code",
        readonly=True,
    )
    project_litigation_level_ids = fields.Many2many(
        "litigation.level",
        string="درجات المشروع المتاحة",
        related="project_id.litigation_level_ids",
        readonly=True,
    )
    total_hours = fields.Float(
        string="إجمالي الساعات",
        compute="_compute_total_hours",
        readonly=True,
    )
    client_document_ids = fields.One2many(
        related="client_id.client_document_ids",
        string="Client Documents",
    )
    pre_litigation_id = fields.Many2one(
        "qlk.pre.litigation",
        string="Pre-Litigation Workflow",
        tracking=True,
    )
    lawyer_id = fields.Many2one(
        "res.users",
        string="Primary Lawyer User",
        related="employee_id.user_id",
        store=True,
        readonly=True,
        index=True,
    )
    completion_identification = fields.Float(string="Identification", compute="_compute_completion_metrics", store=False)
    completion_timeline = fields.Float(string="Timeline", compute="_compute_completion_metrics", store=False)
    completion_parties = fields.Float(string="Parties", compute="_compute_completion_metrics", store=False)
    completion_details = fields.Float(string="Details", compute="_compute_completion_metrics", store=False)
    completion_documents = fields.Float(string="Documents", compute="_compute_completion_metrics", store=False)
    completion_overall = fields.Float(string="Overall Completion", compute="_compute_completion_metrics", store=False)

    @api.depends(
        "project_id.client_code",
        "project_id.litigation_case_number",
        "project_id.case_sequence",
        "project_id.litigation_stage_iteration",
        "project_id.litigation_stage_code",
        "litigation_stage_code",
        "litigation_level_id.code",
    )
    def _compute_project_sequence(self):
        for record in self:
            project = record.project_id
            if not project:
                record.project_sequence = False
                continue
            stage_code = record.litigation_stage_code or project.litigation_stage_code
            record.project_sequence = project._build_litigation_sequence(stage_code)

    @api.depends(
        "project_id",
        "litigation_level_id",
        "task_ids.approval_state",
        "task_ids.hours_spent",
    )
    def _compute_total_hours(self):
        cases = self.filtered("id")
        totals = {case.id: 0.0 for case in cases}
        if cases and "qlk.task" in self.env:
            Task = self.env["qlk.task"]
            task_domain = [("case_id", "in", cases.ids), ("department", "=", "litigation")]
            if "approval_state" in Task._fields:
                task_domain.append(("approval_state", "=", "approved"))
            task_groups = Task.read_group(task_domain, ["hours_spent", "case_id"], ["case_id"])
            for group in task_groups:
                case_ref = group.get("case_id")
                if case_ref:
                    totals[case_ref[0]] = totals.get(case_ref[0], 0.0) + (group.get("hours_spent", 0.0) or 0.0)

        analytic_model = self.env.get("account.analytic.line")
        if cases and analytic_model and "case_id" in analytic_model._fields and "unit_amount" in analytic_model._fields:
            analytic_groups = analytic_model.read_group(
                [("case_id", "in", cases.ids)],
                ["unit_amount", "case_id"],
                ["case_id"],
            )
            for group in analytic_groups:
                case_ref = group.get("case_id")
                if case_ref:
                    totals[case_ref[0]] = totals.get(case_ref[0], 0.0) + (group.get("unit_amount", 0.0) or 0.0)

        for record in self:
            record.total_hours = round(totals.get(record.id, 0.0), 2)

    @api.onchange("project_id")
    def _onchange_project_id(self):
        for record in self:
            project = record.project_id
            if not project:
                continue
            if project.client_id and not record.client_id:
                record.client_id = project.client_id
            if project.company_id and "company_id" in record._fields:
                record.company_id = project.company_id
            if project.company_id.currency_id and "currency_id" in record._fields and not record.currency_id:
                record.currency_id = project.company_id.currency_id
            lawyer = project._get_primary_employee()
            if lawyer and "employee_id" in record._fields and not record.employee_id:
                record.employee_id = lawyer
            if record.litigation_level_id and record.litigation_level_id not in project.litigation_level_ids:
                record.litigation_level_id = False
            if "name2" in record._fields and record.litigation_level_id:
                record.name2 = project._build_litigation_sequence(record.litigation_level_id.code)

    @api.onchange("litigation_level_id")
    def _onchange_litigation_level_id(self):
        for record in self:
            if record.project_id and record.litigation_level_id and "name2" in record._fields:
                record.name2 = record.project_id._build_litigation_sequence(record.litigation_level_id.code)

    @api.constrains("project_id", "litigation_level_id")
    def _check_project_litigation_level(self):
        for record in self:
            project = record.project_id
            if not project:
                continue
            if not record.litigation_level_id:
                raise ValidationError(_("يجب اختيار درجة التقاضي عند ربط القضية بمشروع."))
            if record.litigation_level_id not in project.litigation_level_ids:
                raise ValidationError(
                    _(
                        "درجة التقاضي المختارة غير متاحة في المشروع %(project)s.",
                        project=project.display_name,
                    )
                )
            if project.allow_multiple_cases_per_level:
                continue
            duplicate_domain = [
                ("id", "!=", record.id),
                ("project_id", "=", project.id),
                ("litigation_level_id", "=", record.litigation_level_id.id),
            ]
            if self.search_count(duplicate_domain):
                raise ValidationError(
                    _(
                        "لا يمكن إنشاء أكثر من قضية لنفس درجة التقاضي %(level)s في المشروع %(project)s.",
                        level=record.litigation_level_id.display_name,
                        project=project.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_project_primary_case()
        return records

    def write(self, vals):
        old_projects = {record.id: record.project_id for record in self}
        result = super().write(vals)
        if {"project_id", "litigation_level_id"}.intersection(vals):
            self._sync_project_primary_case(old_projects=old_projects)
        return result

    def _sync_project_primary_case(self, old_projects=None):
        if self.env.context.get("skip_project_primary_case_sync"):
            return
        for record in self:
            project = record.project_id
            if project and not project.case_id:
                project.with_context(skip_project_primary_case_sync=True).write({"case_id": record.id})

            old_project = old_projects and old_projects.get(record.id)
            if old_project and old_project != project and old_project.case_id == record:
                replacement = self.search(
                    [("project_id", "=", old_project.id), ("id", "!=", record.id)],
                    order="id",
                    limit=1,
                )
                old_project.with_context(skip_project_primary_case_sync=True).write(
                    {"case_id": replacement.id if replacement else False}
                )

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
