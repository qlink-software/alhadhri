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
    _rec_name = "service_code"

    task_ids = fields.One2many(
        "project.task",
        "case_id",
        string="Tasks",
    )
    case_hours = fields.Float(
        string="Case Hours",
        compute="_compute_case_hours",
        store=True,
        readonly=True,
    )
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
    engagement_id = fields.Many2one(
        "bd.engagement.letter",
        string="Engagement Letter",
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    project_id = fields.Many2one(
        "qlk.project",
        string="Project",
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('client_file_id', '=', client_file_id), ('service_type', 'in', ['litigation', 'pre_litigation']), ('active', '=', True)]",
    )
    service_code = fields.Char(string="Service Code", readonly=True, copy=False, index=True)
    litigation_degree = fields.Selection(
        [
            ("first", "First Instance"),
            ("appeal", "Appeal"),
            ("cassation", "Cassation"),
        ],
        string="Legacy Litigation Degree",
        tracking=True,
    )
    litigation_level_id = fields.Many2one(
        "litigation.level",
        string="Legacy Litigation Level",
        tracking=True,
        index=True,
    )
    litigation_degree_id = fields.Many2one(
        "qlk.litigation.degree",
        string="Litigation Degree",
        tracking=True,
        index=True,
    )
    allowed_litigation_degree_ids = fields.Many2many(
        "qlk.litigation.degree",
        string="Allowed Litigation Degrees",
        related="project_id.litigation_degree_ids",
        readonly=True,
    )
    litigation_stage_code = fields.Selection(
        selection=LITIGATION_STAGE_CODE_SELECTION,
        string="Stage Code",
        related="litigation_level_id.code",
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

    def init(self):
        super().init()
        cr = self.env.cr
        cr.execute("ALTER TABLE qlk_case ADD COLUMN IF NOT EXISTS service_code varchar")
        cr.execute(
            """
            UPDATE qlk_case c
               SET service_code = p.service_code || '/' || d.code
              FROM qlk_project p, qlk_litigation_degree d
             WHERE c.project_id = p.id
               AND c.litigation_degree_id = d.id
               AND c.service_code IS DISTINCT FROM (p.service_code || '/' || d.code)
               AND p.service_code IS NOT NULL
               AND d.code IS NOT NULL
            """
        )

    @api.depends("task_ids.effective_hours", "task_ids.timesheet_ids.unit_amount")
    def _compute_case_hours(self):
        cases = self.filtered("id")
        totals = {case.id: 0.0 for case in cases}
        if cases:
            groups = self.env["project.task"].read_group(
                [("case_id", "in", cases.ids)],
                ["effective_hours", "case_id"],
                ["case_id"],
            )
            for group in groups:
                case_ref = group.get("case_id")
                if case_ref:
                    totals[case_ref[0]] = group.get("effective_hours", 0.0) or 0.0
        for record in self:
            record.case_hours = round(totals.get(record.id, 0.0), 2)

    @api.depends("case_hours")
    def _compute_total_hours(self):
        for record in self:
            record.total_hours = record.case_hours

    @api.onchange("engagement_id")
    def _onchange_engagement_id(self):
        for record in self:
            engagement = record.engagement_id
            if not engagement:
                continue
            if engagement.partner_id and not record.client_id:
                record.client_id = engagement.partner_id.id
            if engagement.company_id and "company_id" in record._fields:
                record.company_id = engagement.company_id.id
            if engagement.lawyer_employee_id and "employee_id" in record._fields and not record.employee_id:
                record.employee_id = engagement.lawyer_employee_id.id
            if not record.litigation_degree_id and engagement.litigation_degree_ids:
                record.litigation_degree_id = engagement.litigation_degree_ids[:1].id

    @api.onchange("project_id")
    def _onchange_project_id(self):
        for record in self:
            project = record.project_id
            if not project:
                continue
            if project.client_id and not record.client_id:
                record.client_id = project.client_id.id
            if project.client_id and not record.client_ids:
                record.client_ids = [(6, 0, project.client_id.ids)]
            if project.engagement_letter_id and not record.engagement_id:
                record.engagement_id = project.engagement_letter_id.id
            if project.lawyer_id and "employee_id" in record._fields and not record.employee_id:
                record.employee_id = project.lawyer_id.id
            if record.litigation_degree_id and record.litigation_degree_id not in project.litigation_degree_ids:
                record.litigation_degree_id = False
                record.litigation_level_id = False
                record.litigation_degree = False
            record.service_code = record._service_code_from_project_degree(project, record.litigation_degree_id)

    @api.onchange("litigation_degree_id")
    def _onchange_litigation_degree_id(self):
        for record in self:
            degree = record.litigation_degree_id
            if degree and degree.level_id:
                record.litigation_level_id = degree.level_id.id
            record.litigation_degree = record._legacy_litigation_degree_from_degree(degree)
            record.service_code = record._service_code_from_project_degree(record.project_id, degree)

    @api.onchange("litigation_degree")
    def _onchange_legacy_litigation_degree(self):
        for record in self:
            if record.litigation_degree and not record.litigation_degree_id:
                degree = record._degree_from_legacy_litigation_degree(record.litigation_degree)
                if degree:
                    record.litigation_degree_id = degree.id
                    record.litigation_level_id = degree.level_id.id
                    record.service_code = record._service_code_from_project_degree(record.project_id, degree)

    @api.constrains("project_id", "engagement_id", "litigation_degree_id", "litigation_level_id")
    def _check_engagement_case_rules(self):
        if self.env.context.get("skip_engagement_case_validation"):
            return
        for record in self:
            if not record.project_id:
                raise ValidationError(_("Cases must be created from a project."))
            allows_litigation = (
                record.project_id._allows_legal_service("litigation")
                if hasattr(record.project_id, "_allows_legal_service")
                else record.project_id.service_type == "litigation"
            )
            allows_pre_litigation = (
                record.project_id._allows_legal_service("pre_litigation")
                if hasattr(record.project_id, "_allows_legal_service")
                else record.project_id.service_type == "pre_litigation"
            )
            if not allows_litigation and not (allows_pre_litigation and record.pre_litigation_id):
                raise ValidationError(_("This project does not allow litigation case creation."))
            engagement = record.engagement_id or record.project_id.engagement_letter_id
            degree = record.litigation_degree_id
            if not degree and record.litigation_level_id:
                degree = self.env["qlk.litigation.degree"].search(
                    [("level_id", "=", record.litigation_level_id.id)],
                    limit=1,
                )
            if engagement and not degree:
                raise ValidationError(_("Select a litigation degree for this case."))
            allowed_degrees = record.project_id.litigation_degree_ids or engagement.litigation_degree_ids
            if allowed_degrees and degree not in allowed_degrees:
                raise ValidationError(_("The selected litigation degree is not allowed for this project."))
            if degree and record.litigation_level_id and degree.level_id and record.litigation_level_id != degree.level_id:
                raise ValidationError(_("The selected litigation degree does not match the litigation level."))
            if (
                degree
                and record.project_id
                and not self.env.context.get("allow_duplicate_litigation_degree")
                and self.search_count([
                    ("id", "!=", record.id),
                    ("project_id", "=", record.project_id.id),
                    ("litigation_degree_id", "=", degree.id),
                ])
            ):
                raise ValidationError(_("A litigation case already exists for this project and degree."))
            if engagement and engagement.contract_type == "cases" and engagement.agreed_case_count and engagement.remaining_cases < 0:
                raise ValidationError(_("Case limit exceeded for this engagement letter."))

    @api.model
    def _normalize_litigation_degree_vals(self, vals):
        if vals.get("litigation_degree") and not vals.get("litigation_degree_id"):
            degree = self._degree_from_legacy_litigation_degree(vals["litigation_degree"])
            if degree:
                vals["litigation_degree_id"] = degree.id
                if degree.level_id:
                    vals["litigation_level_id"] = degree.level_id.id
        if vals.get("litigation_degree_id"):
            degree = self.env["qlk.litigation.degree"].browse(vals["litigation_degree_id"])
            if degree.exists() and degree.level_id:
                vals["litigation_level_id"] = degree.level_id.id
            if degree.exists():
                vals["litigation_degree"] = self._legacy_litigation_degree_from_degree(degree)
        elif vals.get("litigation_level_id") and not vals.get("litigation_degree_id"):
            degree = self.env["qlk.litigation.degree"].search(
                [("level_id", "=", vals["litigation_level_id"])],
                limit=1,
            )
            if degree:
                vals["litigation_degree_id"] = degree.id
                vals["litigation_degree"] = self._legacy_litigation_degree_from_degree(degree)
        return vals

    @api.model
    def _degree_from_legacy_litigation_degree(self, legacy_degree):
        xmlids = {
            "first": "qlk_management.qlk_litigation_degree_first_instance",
            "appeal": "qlk_management.qlk_litigation_degree_appeal",
            "cassation": "qlk_management.qlk_litigation_degree_cassation",
        }
        xmlid = xmlids.get(legacy_degree)
        return self.env.ref(xmlid, raise_if_not_found=False) if xmlid else self.env["qlk.litigation.degree"]

    @api.model
    def _legacy_litigation_degree_from_degree(self, degree):
        if not degree:
            return False
        if degree.code == "F":
            return "first"
        if degree.code == "A":
            return "appeal"
        if degree.code == "C":
            return "cassation"
        return False

    @api.model
    def _service_code_from_project_degree(self, project, degree):
        if not project or not degree:
            return False
        project._ensure_service_code()
        if not project.service_code or not degree.code:
            return False
        return "%s/%s" % (project.service_code, degree.code)

    @api.model
    def _service_code_from_vals(self, vals):
        project = self.env["qlk.project"].browse(vals.get("project_id"))
        degree = self.env["qlk.litigation.degree"].browse(vals.get("litigation_degree_id"))
        return self._service_code_from_project_degree(project if project.exists() else False, degree if degree.exists() else False)

    @api.model
    def sync_legacy_litigation_degrees(self):
        cases = self.search([
            ("litigation_degree", "!=", False),
            ("litigation_degree_id", "=", False),
        ])
        for case in cases:
            degree = case._degree_from_legacy_litigation_degree(case.litigation_degree)
            if degree:
                case.with_context(skip_engagement_case_validation=True).write({
                    "litigation_degree_id": degree.id,
                    "litigation_level_id": degree.level_id.id if degree.level_id else False,
                })
        cases_without_legacy = self.search([
            ("litigation_degree_id", "!=", False),
            ("litigation_degree", "=", False),
        ])
        for case in cases_without_legacy:
            legacy_degree = case._legacy_litigation_degree_from_degree(case.litigation_degree_id)
            if legacy_degree:
                case.with_context(skip_engagement_case_validation=True).write({
                    "litigation_degree": legacy_degree,
                })
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                raise ValidationError(_("Cases must be created from a project."))
            if vals.get("project_id"):
                self._ensure_project_manager()
            self._apply_project_defaults(vals)
            self._normalize_litigation_degree_vals(vals)
            vals["service_code"] = self._service_code_from_vals(vals)
        records = super().create(vals_list)
        return records

    def write(self, vals):
        if "project_id" in vals:
            if not vals.get("project_id"):
                raise ValidationError(_("Cases must be linked to a project."))
            if vals.get("project_id"):
                self._ensure_project_manager()
                self._apply_project_defaults(vals)
        if {"litigation_degree_id", "litigation_level_id"}.intersection(vals):
            self._normalize_litigation_degree_vals(vals)
        if {"project_id", "litigation_degree_id", "litigation_level_id"}.intersection(vals):
            for record in self:
                merged_vals = {
                    "project_id": vals.get("project_id", record.project_id.id),
                    "litigation_degree_id": vals.get("litigation_degree_id", record.litigation_degree_id.id),
                    "litigation_level_id": vals.get("litigation_level_id", record.litigation_level_id.id),
                }
                self._normalize_litigation_degree_vals(merged_vals)
                vals["service_code"] = self._service_code_from_vals(merged_vals)
        return super().write(vals)

    def _apply_project_defaults(self, vals):
        project_id = vals.get("project_id")
        if not project_id:
            return vals
        project = self.env[self._fields["project_id"].comodel_name].browse(project_id)
        if project.exists():
            vals.setdefault("client_file_id", project.client_file_id.id if "client_file_id" in project._fields else False)
            vals.setdefault("engagement_id", project.engagement_letter_id.id)
            vals.setdefault("client_id", project.client_id.id)
            vals.setdefault("client_ids", [(6, 0, project.client_id.ids)] if project.client_id else False)
            vals.setdefault("employee_id", project.lawyer_id.id)
        return vals

    def _ensure_project_manager(self):
        project_model = self.env[self._fields["project_id"].comodel_name]
        if hasattr(project_model, "_ensure_legal_manager"):
            return project_model._ensure_legal_manager()
        return True

    def action_open_project_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tasks"),
            "res_model": "project.task",
            "view_mode": "list,form",
            "domain": [("case_id", "=", self.id)],
            "context": {
                "default_case_id": self.id,
                "default_partner_id": self.client_id.id,
                "qlk_require_case_id": True,
            },
        }

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
