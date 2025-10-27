# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError


class QlkProject(models.Model):
    _name = "qlk.project"
    _description = "Legal Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string="Project Code", compute="_compute_code", store=True, tracking=True)
    reference = fields.Char(string="Reference", copy=False, tracking=True)
    department = fields.Selection(
        selection=[
            ("pre_litigation", "Pre-Litigation"),
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
        ],
        required=True,
        default="pre_litigation",
        tracking=True,
    )
    stage_id = fields.Many2one(
        "qlk.project.stage",
        string="Stage",
        required=True,
        tracking=True,
        domain="[('stage_type', '=', stage_type_code)]",
    )
    stage_type_code = fields.Selection(
        selection=[
            ("pre_litigation", "Pre-Litigation"),
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
        ],
        compute="_compute_stage_type_code",
        store=True,
    )
    case_sequence = fields.Integer(
        string="Matter Index",
        copy=False,
        tracking=True,
        help="Three-digit number unique per client and department used in the project code.",
    )
    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        required=True,
        tracking=True,
        domain="[('customer', '=', True), ('parent_id', '=', False)]",
    )
    engagement_id = fields.Many2one("qlk.engagement.letter", string="Engagement Letter", tracking=True)
    case_id = fields.Many2one("qlk.case", string="Linked Court Case", tracking=True, ondelete="set null")
    client_code = fields.Char(string="Client Code", compute="_compute_client_code", store=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    assigned_employee_ids = fields.Many2many(
        "hr.employee",
        string="Assigned Lawyers",
        relation="qlk_project_employee_rel",
        column1="project_id",
        column2="employee_id",
        tracking=True,
    )
    owner_id = fields.Many2one("res.users", string="Project Owner", default=lambda self: self.env.user, tracking=True)
    description = fields.Html()
    poa_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("received", "Received"),
            ("uploaded", "Uploaded"),
        ],
        string="POA Status",
        default="draft",
        tracking=True,
    )
    poa_attachment_ids = fields.Many2many(
        "ir.attachment", "qlk_project_poa_rel", "project_id", "attachment_id", string="POA Documents"
    )
    poa_requested_on = fields.Datetime(string="POA Requested On")
    poa_received_on = fields.Datetime(string="POA Received On")
    active = fields.Boolean(default=True)
    notes = fields.Text()
    stage_log_ids = fields.One2many("qlk.project.stage.log", "project_id", string="Stage History")
    stage_log_count = fields.Integer(compute="_compute_stage_log_count")
    stage_started_on = fields.Datetime(string="Stage Started On", tracking=True)
    stage_completed_on = fields.Datetime(string="Stage Completed On")
    task_ids = fields.One2many("qlk.task", "project_id", string="Tasks")
    task_hours_total = fields.Float(
        string="Approved Hours",
        compute="_compute_task_hours",
        readonly=True,
    )
    task_hours_month = fields.Float(
        string="Approved Hours (Month)",
        compute="_compute_task_hours",
        readonly=True,
    )
    translation_task_id = fields.Many2one(
        "qlk.task",
        string="Translation Task",
        help="Automatically generated translation task for pre-litigation workflow.",
    )
    deadline = fields.Date(string="Overall Deadline")
    color = fields.Integer(string="Color Index")
    pre_litigation_channel = fields.Boolean(
        string="Pre-Litigation Channel",
        help="Indicates the matter is being prepared before registration in court.",
    )
    transfer_ready = fields.Boolean(
        string="Ready to Transfer",
        help="Checked when all required stages are completed and case details can be submitted.",
    )

    _sql_constraints = [
        ("qlk_project_code_unique", "unique(code)", "The project code must be unique."),
    ]

    def name_get(self):
        result = []
        for project in self:
            name = project.name
            if project.code:
                name = f"{project.code} - {name}"
            result.append((project.id, name))
        return result

    @api.depends("department")
    def _compute_stage_type_code(self):
        for project in self:
            project.stage_type_code = project.department or "pre_litigation"

    @api.onchange("department")
    def _onchange_department(self):
        if not self.department:
            return
        stage = self.env["qlk.project.stage"].search(
            [
                ("stage_type", "=", self.department),
            ],
            order="sequence asc",
            limit=1,
        )
        if stage:
            self.stage_id = stage.id
        self.pre_litigation_channel = self.department == "pre_litigation"

    @api.depends("client_id", "engagement_id.client_unique_code")
    def _compute_client_code(self):
        for project in self:
            code = project.engagement_id.client_unique_code
            if not code and project.client_id:
                code = project.client_id.ref or f"{project.client_id.id:03d}"
            project.client_code = code or ""

    @api.depends("stage_id", "case_sequence", "department", "client_code")
    def _compute_code(self):
        for project in self:
            client_code = project.client_code or "PRJ"
            sequence = project.case_sequence or 1
            stage = project.stage_id
            if not stage:
                project.code = f"{client_code}/PR{sequence:03d}"
                continue

            if project.department == "litigation":
                suffix = stage.stage_code or "F"
                if stage.stage_number:
                    project.code = f"{client_code}/L{sequence:03d}-{stage.stage_number}/{suffix}"
                else:
                    project.code = f"{client_code}/L{sequence:03d}/{suffix}"
            elif project.department == "pre_litigation":
                suffix = stage.stage_code or (stage.technical_code or "PL")
                project.code = f"{client_code}/PL{sequence:03d}/{suffix}"
            elif project.department == "corporate":
                suffix = stage.stage_code or (stage.technical_code or "COR")
                project.code = f"{client_code}/C{sequence:03d}/{suffix}"
            else:  # arbitration
                suffix = stage.stage_code or (stage.technical_code or "ARB")
                project.code = f"{client_code}/A{sequence:03d}/{suffix}"

    @api.depends("stage_log_ids")
    def _compute_stage_log_count(self):
        for project in self:
            project.stage_log_count = len(project.stage_log_ids)

    @api.depends("task_ids.approval_state", "task_ids.hours_spent", "task_ids.date_start")
    def _compute_task_hours(self):
        approved_states = {"approved"}
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for project in self:
            total = 0.0
            month_total = 0.0
            for task in project.task_ids:
                if task.approval_state in approved_states:
                    total += task.hours_spent
                    if task.date_start and task.date_start >= month_start:
                        month_total += task.hours_spent
            project.task_hours_total = total
            project.task_hours_month = month_total

    @api.model_create_multi
    def create(self, vals_list):
        stage_model = self.env["qlk.project.stage"]
        res = []
        for vals in vals_list:
            department = vals.get("department") or "pre_litigation"
            if "pre_litigation_channel" not in vals and department == "pre_litigation":
                vals["pre_litigation_channel"] = True
            if not vals.get("stage_id"):
                default_stage = stage_model.search(
                    [("stage_type", "=", department), ("is_default", "=", True)], order="sequence asc", limit=1
                )
                if not default_stage:
                    default_stage = stage_model.search(
                        [("stage_type", "=", department)], order="sequence asc", limit=1
                    )
                if not default_stage:
                    raise UserError(
                        _("No stage configured for the %(dept)s department.") % {"dept": department.replace("_", " ").title()}
                    )
                vals["stage_id"] = default_stage.id

            client_id = vals.get("client_id")
            if client_id and not vals.get("case_sequence"):
                vals["case_sequence"] = self._next_case_sequence(client_id, vals.get("department"))

            res.append(vals)

        projects = super().create(res)
        projects._init_stage_logs()
        projects._post_create_notifications()
        projects._ensure_translation_task()
        return projects

    def write(self, vals):
        tracked_stage = "stage_id" in vals
        # capture original stages before write
        previous_stage = {project.id: project.stage_id for project in self} if tracked_stage else {}
        result = super().write(vals)
        if tracked_stage:
            new_stage_id = vals.get("stage_id")
            new_stage = self.env["qlk.project.stage"].browse(new_stage_id) if new_stage_id else False
            for project in self:
                if previous_stage.get(project.id) != project.stage_id:
                    project._handle_stage_transition(previous_stage.get(project.id), project.stage_id)
        if "assigned_employee_ids" in vals:
            self._notify_assignment_changes()
        if "department" in vals:
            # potentially re-align default stage type and translation task
            self._ensure_translation_task()
        return result

    def _next_case_sequence(self, client_id, department):
        domain = [("client_id", "=", client_id), ("department", "=", department)]
        latest = self.search(domain, order="case_sequence desc", limit=1)
        return (latest.case_sequence or 0) + 1

    def _init_stage_logs(self):
        StageLog = self.env["qlk.project.stage.log"]
        now = fields.Datetime.now()
        for project in self:
            StageLog.create(
                {
                    "project_id": project.id,
                    "stage_id": project.stage_id.id,
                    "date_start": now,
                }
            )
            project.stage_started_on = now

    def _handle_stage_transition(self, previous_stage, new_stage):
        StageLog = self.env["qlk.project.stage.log"]
        now = fields.Datetime.now()
        if previous_stage:
            log = StageLog.search(
                [("project_id", "=", self.id), ("stage_id", "=", previous_stage.id), ("date_end", "=", False)],
                limit=1,
            )
            if log:
                log.write({"date_end": now, "completed_by": self.env.user.id})
        StageLog.create(
            {
                "project_id": self.id,
                "stage_id": new_stage.id,
                "date_start": now,
            }
        )
        self.stage_started_on = now
        self.stage_completed_on = False
        self.transfer_ready = new_stage.technical_code == "ready_litigation"
        self._ensure_translation_task()
        self._notify_stage_change(previous_stage, new_stage)

    def _post_create_notifications(self):
        for project in self:
            if project.assigned_employee_ids:
                partners = project.assigned_employee_ids.mapped("user_id.partner_id")
                if partners:
                    project.message_subscribe(partner_ids=partners.ids)
                    project.message_post(
                        body=_("Project %(code)s has been created and assigned to you.", code=project.code),
                        partner_ids=partners.ids,
                    )

    def _notify_assignment_changes(self):
        for project in self:
            partners = project.assigned_employee_ids.mapped("user_id.partner_id")
            if partners:
                project.message_subscribe(partner_ids=partners.ids)
                project.message_post(
                    body=_("Project team updated."),
                    partner_ids=partners.ids,
                )

    def _notify_stage_change(self, previous_stage, new_stage):
        if not self.assigned_employee_ids:
            return
        partners = self.assigned_employee_ids.mapped("user_id.partner_id")
        if not partners:
            return
        previous_name = previous_stage.name if previous_stage else _("New")
        body = _(
            "Project %(code)s moved from %(previous)s to %(current)s.",
            code=self.code,
            previous=previous_name,
            current=new_stage.name,
        )
        self.message_post(body=body, partner_ids=partners.ids)

    def action_request_poa(self):
        for project in self:
            project.write(
                {
                    "poa_state": "requested",
                    "poa_requested_on": fields.Datetime.now(),
                }
            )
            project.message_post(body=_("POA has been requested from the client."))

    def action_mark_poa_received(self):
        for project in self:
            project.write(
                {
                    "poa_state": "received",
                    "poa_received_on": fields.Datetime.now(),
                }
            )
            project.message_post(body=_("POA received and pending upload."))

    def action_mark_poa_uploaded(self):
        for project in self:
            state = "uploaded" if project.poa_attachment_ids else "received"
            project.write({"poa_state": state})
            if state == "uploaded":
                project.message_post(body=_("POA documents uploaded."))

    def action_view_stage_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Stage History"),
            "res_model": "qlk.project.stage.log",
            "view_mode": "tree,form",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id},
        }

    def action_view_tasks(self):
        self.ensure_one()
        action = self.env.ref("qlk_task_management.action_qlk_task_all").read()[0]
        context = action.get("context") or {}
        if isinstance(context, str):
            context = safe_eval(context)
        context.update(
            {
                "default_project_id": self.id,
                "default_department": self.department if self.department in {"litigation", "corporate"} else "pre_litigation",
                "search_default_group_month": 1,
            }
        )
        action["context"] = context
        action["domain"] = [("project_id", "=", self.id)]
        return action

    def _ensure_translation_task(self):
        """Ensure the mandatory translation task exists whenever the project is in the translation stage."""
        translation_stage_codes = {"translation"}
        Task = self.env["qlk.task"]
        for project in self:
            stage = project.stage_id
            if stage and stage.technical_code in translation_stage_codes:
                if not project.translation_task_id or project.translation_task_id not in project.task_ids:
                    vals = project._prepare_standard_task(stage, technical_code="translation")
                    task = Task.create(vals)
                    project.translation_task_id = task.id
            else:
                # keep pointer but do not delete task - user may still need it
                continue

    def _prepare_standard_task(self, stage, technical_code=None):
        employee = self.assigned_employee_ids[:1]
        if not employee and self.owner_id and self.owner_id.employee_ids:
            employee = self.owner_id.employee_ids[:1]
        if not employee and self.env.user.employee_ids:
            employee = self.env.user.employee_ids[:1]
        if not employee:
            raise UserError(
                _("Assign at least one lawyer to the project before generating standard tasks."))
        reviewer = self.owner_id or self.env.user
        department = (
            "corporate"
            if self.department == "corporate"
            else ("litigation" if self.department == "litigation" else "pre_litigation")
        )
        description = ""
        if technical_code == "translation":
            description = _(
                "Centralised translation workflow.\n"
                "- Upload documents requiring translation.\n"
                "- Office Manager to coordinate translators.\n"
                "- Uploaded translations will notify the assigned lawyers."
            )
        return {
            "name": stage.auto_task_name or stage.name,
            "department": department,
            "project_id": self.id,
            "employee_id": employee.id,
            "reviewer_id": reviewer.id,
            "description": description,
            "hours_spent": 1.0,
            "date_start": fields.Date.context_today(self),
        }

    def action_transfer_to_litigation(self):
        self.ensure_one()
        if self.department not in {"pre_litigation", "litigation"}:
            raise UserError(_("Only pre-litigation or litigation projects can be transferred to a court case."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "qlk.project.transfer.litigation",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
                "default_client_id": self.client_id.id,
                "default_assigned_employee_id": self.assigned_employee_ids[:1].id if self.assigned_employee_ids else False,
            },
        }

    def action_mark_stage_completed(self):
        for project in self:
            project.stage_completed_on = fields.Datetime.now()
            project.message_post(body=_("Stage %(stage)s marked completed.", stage=project.stage_id.name))

    def action_next_stage(self):
        for project in self:
            next_stage = self.env["qlk.project.stage"].search(
                [
                    ("stage_type", "=", project.stage_type_code),
                    ("sequence", ">", project.stage_id.sequence),
                ],
                order="sequence asc",
                limit=1,
            )
            if not next_stage:
                raise UserError(_("No further stages configured for this project."))
            project.stage_id = next_stage.id

    def action_previous_stage(self):
        for project in self:
            previous_stage = self.env["qlk.project.stage"].search(
                [
                    ("stage_type", "=", project.stage_type_code),
                    ("sequence", "<", project.stage_id.sequence),
                ],
                order="sequence desc",
                limit=1,
            )
            if not previous_stage:
                raise UserError(_("Already at the first stage."))
            project.stage_id = previous_stage.id
