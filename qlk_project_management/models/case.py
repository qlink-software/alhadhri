# -*- coding: utf-8 -*-
from psycopg2.errors import UndefinedTable
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import sql

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
        "client_document_ids",
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
    stage_id = fields.Many2one(
        "qlk.project.stage",
        string="Stage",
        required=True,
        tracking=True,
        domain="[('stage_type', '=', litigation_flow)]",
        default=lambda self: self._default_case_stage("pre_litigation"),
    )
    stage_started_on = fields.Datetime(string="Stage Started On", tracking=True)
    stage_completed_on = fields.Datetime(string="Stage Completed On")
    stage_log_ids = fields.One2many("qlk.case.stage.log", "case_id", string="Stage History")
    stage_log_count = fields.Integer(compute="_compute_stage_log_count")
    client_capacity = fields.Char(string="Client Capacity/Title")
    client_document_ids = fields.One2many(
        related="client_id.client_document_ids",
        string="Client Documents",
        readonly=True,
    )
    client_document_warning = fields.Html(
        related="client_id.document_warning_message",
        readonly=True,
    )
    client_document_warning_required = fields.Boolean(
        related="client_id.document_warning_required",
        readonly=True,
    )
    completion_identification = fields.Float(string="Identification", compute="_compute_completion_metrics", store=False)
    completion_timeline = fields.Float(string="Timeline", compute="_compute_completion_metrics", store=False)
    completion_parties = fields.Float(string="Parties", compute="_compute_completion_metrics", store=False)
    completion_details = fields.Float(string="Details", compute="_compute_completion_metrics", store=False)
    completion_documents = fields.Float(string="Documents", compute="_compute_completion_metrics", store=False)
    completion_overall = fields.Float(string="Overall Completion", compute="_compute_completion_metrics", store=False)

    @api.model
    def _default_case_stage(self, flow):
        Stage = self.env["qlk.project.stage"]
        if not sql.table_exists(self.env.cr, Stage._table):
            return Stage.browse()

        try:
            default_stage = Stage.search(
                [("stage_type", "=", flow), ("is_default", "=", True)],
                order="sequence asc",
                limit=1,
            )
            if not default_stage:
                default_stage = Stage.search(
                    [("stage_type", "=", flow)],
                    order="sequence asc",
                    limit=1,
                )
        except UndefinedTable:
            return Stage.browse()
        if not default_stage and not self.env.context.get("install_mode"):
            raise UserError(
                _("No stages configured for the %(flow)s pipeline.") % {
                    "flow": dict(self._fields["litigation_flow"].selection).get(flow, flow.replace("_", " ").title()),
                }
            )
        return default_stage

    @api.depends("stage_log_ids")
    def _compute_stage_log_count(self):
        for record in self:
            record.stage_log_count = len(record.stage_log_ids)

    @api.onchange("litigation_flow")
    def _onchange_litigation_flow(self):
        if not self.litigation_flow:
            return
        stage = self._default_case_stage(self.litigation_flow)
        self.stage_id = stage.id

    @api.model_create_multi
    def create(self, vals_list):
        res = []
        for vals in vals_list:
            flow = vals.get("litigation_flow") or "pre_litigation"
            if not vals.get("stage_id"):
                stage = self._default_case_stage(flow)
                if stage:
                    vals["stage_id"] = stage.id
            res.append(vals)
        records = super().create(res)
        records._init_stage_logs()
        return records

    def write(self, vals):
        tracked_stage = "stage_id" in vals
        previous_stage = {record.id: record.stage_id for record in self} if tracked_stage else {}

        if "litigation_flow" in vals and "stage_id" not in vals:
            flow = vals["litigation_flow"]
            stage = self._default_case_stage(flow)
            if stage:
                vals["stage_id"] = stage.id

        result = super().write(vals)

        if tracked_stage:
            for record in self:
                if previous_stage.get(record.id) != record.stage_id:
                    record._handle_stage_transition(previous_stage.get(record.id), record.stage_id)
        return result

    def _init_stage_logs(self):
        StageLog = self.env["qlk.case.stage.log"]
        now = fields.Datetime.now()
        for record in self:
            if not record.stage_id:
                continue
            StageLog.create(
                {
                    "case_id": record.id,
                    "stage_id": record.stage_id.id,
                    "date_start": now,
                }
            )
            record.stage_started_on = now

    def _handle_stage_transition(self, previous_stage, new_stage):
        StageLog = self.env["qlk.case.stage.log"]
        now = fields.Datetime.now()
        if previous_stage:
            log = StageLog.search(
                [
                    ("case_id", "=", self.id),
                    ("stage_id", "=", previous_stage.id),
                    ("date_end", "=", False),
                ],
                limit=1,
            )
            if log:
                log.write({"date_end": now, "completed_by": self.env.user.id})
        if new_stage:
            StageLog.create(
                {
                    "case_id": self.id,
                    "stage_id": new_stage.id,
                    "date_start": now,
                }
            )
            self.stage_started_on = now
            self.stage_completed_on = False
            self._notify_stage_change(previous_stage, new_stage)

    def _notify_stage_change(self, previous_stage, new_stage):
        previous_name = previous_stage.name if previous_stage else _("New")
        body = _(
            "Case %(case)s moved from %(previous)s to %(current)s.",
            case=self.display_name,
            previous=previous_name,
            current=new_stage.name if new_stage else _("Undefined"),
        )
        self.message_post(body=body)

    def action_case_mark_stage_completed(self):
        for record in self:
            record.stage_completed_on = fields.Datetime.now()
            record.message_post(body=_("Stage %(stage)s marked completed.", stage=record.stage_id.name))

    def _move_stage(self, direction):
        Stage = self.env["qlk.project.stage"]
        for record in self:
            if not record.stage_id:
                raise UserError(_("Please assign a stage before moving through the pipeline."))
            domain = [
                ("stage_type", "=", record.litigation_flow),
            ]
            if direction == "next":
                domain.append(("sequence", ">", record.stage_id.sequence))
                order = "sequence asc"
            else:
                domain.append(("sequence", "<", record.stage_id.sequence))
                order = "sequence desc"
            next_stage = Stage.search(domain, order=order, limit=1)
            if not next_stage:
                raise UserError(_("No additional stages available for this pipeline."))
            record.stage_id = next_stage.id

    def action_case_next_stage(self):
        self._move_stage("next")

    def action_case_previous_stage(self):
        self._move_stage("previous")

    def action_view_case_stage_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Stage History"),
            "res_model": "qlk.case.stage.log",
            "view_mode": "list,form",
            "domain": [("case_id", "=", self.id)],
            "context": {"default_case_id": self.id},
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
