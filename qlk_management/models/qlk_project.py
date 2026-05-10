# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


SERVICE_TYPE_SELECTION = [
    ("litigation", "Litigation"),
    ("corporate", "Corporate"),
    ("arbitration", "Arbitration"),
    ("pre_litigation", "Pre-Litigation"),
]

CONTRACT_TYPE_SELECTION = [
    ("hours", "Hours Based"),
    ("cases", "Case Based"),
    ("retainer", "Retainer"),
    ("lump_sum", "Lump Sum"),
]

BILLING_TYPE_SELECTION = [
    ("free", "Pro bono"),
    ("paid", "Paid"),
]

LEGAL_MANAGER_GROUPS = (
    "qlk_management.group_bd_manager",
    "qlk_management.group_el_manager",
    "qlk_management.group_client_file_manager",
    "qlk_management.group_project_manager",
)

LEGAL_SERVICE_CODE_PREFIX = {
    "litigation": "L",
    "arbitration": "A",
    "corporate": "C",
    "pre_litigation": "P",
}


class QlkProject(models.Model):
    _name = "qlk.project"
    _description = "QLK Legal Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Project Name", required=True, default=lambda self: _("New Project"), tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("on_hold", "On Hold"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        required=True,
        index=True,
        tracking=True,
        domain="[('customer_rank', '>', 0)]",
    )
    engagement_letter_id = fields.Many2one(
        "bd.engagement.letter",
        string="Engagement Letter",
        copy=False,
        index=True,
        ondelete="set null",
        tracking=True,
    )
    lawyer_id = fields.Many2one(
        "hr.employee",
        string="Lawyer",
        domain="[('user_id.partner_id.is_lawyer', '=', True)]",
        tracking=True,
    )
    service_type = fields.Selection(
        selection=SERVICE_TYPE_SELECTION,
        string="Service Type",
        tracking=True,
        help="Legacy single-service value kept only for migration compatibility. Use Legal Services.",
    )

    contract_type = fields.Selection(selection=CONTRACT_TYPE_SELECTION, string="Contract Type", tracking=True)
    billing_type = fields.Selection(selection=BILLING_TYPE_SELECTION, string="Billing Type", tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    retainer_type = fields.Selection(
        [
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
            ("litigation_corporate", "Litigation + Corporate"),
            ("management_corporate", "Management Corporate"),
            ("management_litigation", "Management Litigation"),
        ],
        string="Retainer Type",
        tracking=True,
    )
    agreed_hours = fields.Float(string="Agreed Hours", tracking=True)
    total_hours = fields.Float(string="Total Hours", tracking=True)
    start_date = fields.Date(string="Start Date", tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    contact_person_ids = fields.Many2many(
        "hr.employee",
        "qlk_project_contact_person_rel",
        "project_id",
        "employee_id",
        string="Contact Persons",
        tracking=True,
    )
    responsible_user_ids = fields.Many2many(
        "res.users",
        "qlk_project_responsible_user_rel",
        "project_id",
        "user_id",
        string="Responsible Users",
        tracking=True,
    )
    phone = fields.Char(string="Phone", tracking=True)
    timesheet_project_id = fields.Many2one(
        "project.project",
        string="Timesheet Project",
        copy=False,
        readonly=True,
        ondelete="set null",
        help="Technical Odoo project used by timesheets on legal tasks.",
    )

    description = fields.Text(string="Description")
    scope_details = fields.Text(string="Scope Details")
    contract_terms = fields.Text(string="Contract Terms")
    payment_terms = fields.Char(string="Payment Terms", tracking=True)
    notes = fields.Text(string="Notes", tracking=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_project_attachment_rel",
        "project_id",
        "attachment_id",
        string="Attachments",
        tracking=True,
    )
    translation_attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_project_translation_attachment_rel",
        "project_id",
        "attachment_id",
        string="Translation Attachments",
        tracking=True,
    )

    planned_hours = fields.Float(string="Planned Hours", tracking=True)
    manual_consumed_hours = fields.Float(string="Manual Consumed Hours", tracking=True)
    consumed_hours = fields.Float(string="Consumed Hours", compute="_compute_hours", store=True, compute_sudo=True)
    remaining_hours = fields.Float(string="Remaining Hours", compute="_compute_hours", store=True, compute_sudo=True)
    overconsumed_hours = fields.Float(string="Overconsumed Hours", compute="_compute_hours", store=True, compute_sudo=True)
    hours_usage_percent = fields.Float(string="Hours Usage %", compute="_compute_hours", store=True, compute_sudo=True)
    hours_state = fields.Selection(
        [
            ("normal", "Normal"),
            ("warning", "Warning"),
            ("danger", "Overconsumed"),
        ],
        string="Hours State",
        compute="_compute_hours",
        compute_sudo=True,
        store=True,
    )

    litigation_degree_ids = fields.Many2many(
        "qlk.litigation.degree",
        "qlk_project_litigation_degree_rel",
        "project_id",
        "degree_id",
        string="Litigation Degrees",
        tracking=True,
    )

    client_name = fields.Char(string="Client Name", related="client_id.name", readonly=True)
    client_code = fields.Char(string="Client Code", compute="_compute_client_profile", store=True)
    service_code = fields.Char(string="Service Code", readonly=True, copy=False, index=True)
    mobile = fields.Char(string="Mobile", related="client_id.mobile", readonly=True)
    email = fields.Char(string="Email", related="client_id.email", readonly=True)
    qid_cr = fields.Char(string="QID / CR", compute="_compute_client_profile", store=True)
    address = fields.Text(string="Address", compute="_compute_address")

    project_task_ids = fields.One2many("project.task", "qlk_project_id", string="Tasks")
    qlk_task_ids = fields.One2many("qlk.task", "project_id", string="Legal Tasks")
    case_ids = fields.One2many("qlk.case", "project_id", string="Cases")
    corporate_case_ids = fields.One2many("qlk.corporate.case", "project_id", string="Corporate")
    arbitration_case_ids = fields.One2many("qlk.arbitration.case", "project_id", string="Arbitration")
    pre_litigation_ids = fields.One2many("qlk.pre.litigation", "project_id", string="Pre-Litigation")
    case_count = fields.Integer(string="Cases", compute="_compute_service_counts", compute_sudo=True)
    corporate_count = fields.Integer(string="Corporate", compute="_compute_service_counts", compute_sudo=True)
    arbitration_count = fields.Integer(string="Arbitration", compute="_compute_service_counts", compute_sudo=True)
    pre_litigation_count = fields.Integer(string="Pre-Litigation", compute="_compute_service_counts", compute_sudo=True)
    task_count = fields.Integer(string="Tasks", compute="_compute_task_count", compute_sudo=True)
    hearing_count = fields.Integer(string="Hearings", compute="_compute_dashboard_counts", compute_sudo=True)
    memo_count = fields.Integer(string="Memos", compute="_compute_dashboard_counts", compute_sudo=True)
    recent_activity_summary = fields.Text(string="Recent Activities", compute="_compute_dashboard_counts", compute_sudo=True)

    _sql_constraints = [
        (
            "engagement_letter_unique",
            "unique(engagement_letter_id)",
            "A project already exists for this engagement letter.",
        ),
    ]

    @api.model
    def _is_legal_manager(self):
        return self.env.is_superuser() or any(self.env.user.has_group(group) for group in LEGAL_MANAGER_GROUPS)

    @api.model
    def _ensure_legal_manager(self):
        if not self._is_legal_manager():
            raise UserError(_("Only Managers or Assistant Managers can perform this action."))
        return True

    def _build_service_code(self, client_code, service_type):
        if not client_code or not service_type:
            return False
        prefix = LEGAL_SERVICE_CODE_PREFIX.get(service_type)
        if not prefix:
            return False
        return "%s%s" % (prefix, self._get_service_client_sequence(client_code))

    @api.model
    def _get_service_client_sequence(self, client_code):
        code = (client_code or "").strip()
        for separator in ("/", "-"):
            if separator in code:
                parts = [part for part in code.split(separator) if part]
                if parts:
                    return parts[-1]
        return code

    def _ensure_service_code(self):
        # Service codes are now generated on the legal service records themselves.
        return True

    def _legal_service_codes(self):
        self.ensure_one()
        services = self.legal_service_type_ids if "legal_service_type_ids" in self._fields else self.env["qlk.legal.service.type"]
        codes = set(services.mapped("code"))
        if not codes and self.service_type:
            codes.add(self.service_type)
        return codes

    def _allows_legal_service(self, service_code):
        self.ensure_one()
        return service_code in self._legal_service_codes()

    def _get_or_create_timesheet_project(self):
        self.ensure_one()
        if self.timesheet_project_id:
            return self.timesheet_project_id
        Project = self.env["project.project"].sudo()
        vals = {
            "name": self.service_code or self.name or _("Legal Project"),
            "client_id": self.client_id.id,
        }
        if "allow_timesheets" in Project._fields:
            vals["allow_timesheets"] = True
        if "company_id" in Project._fields:
            vals["company_id"] = self.env.company.id
        timesheet_project = Project.with_context(
            mail_create_nosubscribe=True,
            mail_auto_subscribe_no_notify=True,
            mail_notrack=True,
        ).create(vals)
        self.sudo().with_context(
            mail_create_nosubscribe=True,
            mail_auto_subscribe_no_notify=True,
            mail_notrack=True,
        ).write({"timesheet_project_id": timesheet_project.id})
        return timesheet_project

    @api.depends("client_id", "client_id.code", "client_id.vat", "client_id.company_registry", "client_id.ref")
    def _compute_client_profile(self):
        for project in self:
            client = project.client_id
            project.client_code = client._get_client_code() if client else False
            project.qid_cr = client.vat or client.company_registry or client.ref if client else False

    @api.depends(
        "planned_hours",
        "manual_consumed_hours",
        "case_ids.case_hours",
        "pre_litigation_ids.hours_used",
        "corporate_case_ids.actual_hours_total",
        "arbitration_case_ids.actual_hours_total",
        "qlk_task_ids.hours_spent",
        "qlk_task_ids.approval_state",
        "project_task_ids.effective_hours",
        "project_task_ids.timesheet_ids.unit_amount",
    )
    def _compute_hours(self):
        for project in self:
            approved_qlk_task_hours = sum(
                project.qlk_task_ids.filtered(lambda task: task.approval_state == "approved").mapped("hours_spent")
            )
            service_hours = (
                sum(project.case_ids.mapped("case_hours"))
                + sum(project.pre_litigation_ids.mapped("hours_used"))
                + sum(project.corporate_case_ids.mapped("actual_hours_total"))
                + sum(project.arbitration_case_ids.mapped("actual_hours_total"))
            )
            timesheet_hours = sum(project.project_task_ids.mapped("effective_hours"))
            # الساعات المركزية تجمع الخدمات القانونية والمهام المعتمدة والتايم شيت مع الإدخال اليدوي عند الحاجة.
            consumed = (project.manual_consumed_hours or 0.0) + service_hours + approved_qlk_task_hours + timesheet_hours
            project.consumed_hours = consumed
            project.remaining_hours = (project.planned_hours or 0.0) - consumed
            project.overconsumed_hours = abs(project.remaining_hours) if project.remaining_hours < 0 else 0.0
            project.hours_usage_percent = (
                round((consumed / project.planned_hours) * 100.0, 2) if project.planned_hours else 0.0
            )
            if project.remaining_hours < 0:
                project.hours_state = "danger"
            elif project.planned_hours and project.hours_usage_percent >= 80.0:
                project.hours_state = "warning"
            else:
                project.hours_state = "normal"

    @api.depends(
        "case_ids",
        "corporate_case_ids",
        "arbitration_case_ids",
        "pre_litigation_ids",
    )
    def _compute_service_counts(self):
        for project in self:
            project.case_count = len(project.case_ids)
            project.corporate_count = len(project.corporate_case_ids)
            project.arbitration_count = len(project.arbitration_case_ids)
            project.pre_litigation_count = len(project.pre_litigation_ids)

    @api.depends("project_task_ids")
    def _compute_task_count(self):
        for project in self:
            project.task_count = len(project.project_task_ids) + len(project.qlk_task_ids)

    @api.depends(
        "case_ids",
        "arbitration_case_ids.session_ids",
        "arbitration_case_ids.memo_ids",
        "corporate_case_ids.memo_ids",
        "message_ids",
    )
    def _compute_dashboard_counts(self):
        for project in self:
            project.hearing_count = len(project.arbitration_case_ids.mapped("session_ids"))
            project.memo_count = len(project.arbitration_case_ids.mapped("memo_ids")) + len(project.corporate_case_ids.mapped("memo_ids"))
            messages = project.message_ids.sorted("date", reverse=True)[:5]
            activity_lines = [
                (message.subject or message.body or "").strip()
                for message in messages
                if (message.subject or message.body)
            ]
            project.recent_activity_summary = "\n".join(activity_lines[:5])

    @api.depends(
        "client_id",
        "client_id.street",
        "client_id.street2",
        "client_id.city",
        "client_id.state_id",
        "client_id.zip",
        "client_id.country_id",
    )
    def _compute_address(self):
        for project in self:
            project.address = project.client_id._display_address() if project.client_id else False

    @api.onchange("agreed_hours")
    def _onchange_agreed_hours(self):
        for project in self:
            if not project.planned_hours:
                project.planned_hours = project.agreed_hours

    @api.model_create_multi
    def create(self, vals_list):
        self._ensure_legal_manager()
        for vals in vals_list:
            if not vals.get("client_id"):
                raise ValidationError(_("Cannot create project without client."))
            if not vals.get("name") or vals.get("name") == _("New Project"):
                vals["name"] = self.env["ir.sequence"].next_by_code("qlk.project") or _("New Project")
            if vals.get("engagement_letter_id"):
                existing = self.search([("engagement_letter_id", "=", vals["engagement_letter_id"])], limit=1)
                if existing:
                    raise ValidationError(_("A project already exists for this engagement letter."))
            vals.setdefault("planned_hours", vals.get("agreed_hours") or 0.0)
        projects = super(
            QlkProject,
            self.with_context(
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
            ),
        ).create(vals_list)
        projects._notify_project_created()
        return projects

    def write(self, vals):
        previous_remaining = {project.id: project.remaining_hours for project in self}
        if any(field in vals for field in ("client_id", "service_type", "legal_service_type_ids", "engagement_letter_id")):
            self._ensure_legal_manager()
        result = super().write(vals)
        if {"planned_hours", "manual_consumed_hours"}.intersection(vals):
            self._notify_hours_threshold(previous_remaining=previous_remaining)
        return result

    @api.constrains("client_id", "service_type", "litigation_degree_ids")
    def _check_project_rules(self):
        for project in self:
            if not project.client_id:
                raise ValidationError(_("Cannot create project without client."))
            if project._allows_legal_service("litigation") and not project.litigation_degree_ids:
                raise ValidationError(_("Litigation degree is required for litigation projects."))

    def _service_context(self):
        self.ensure_one()
        self._ensure_service_code()
        return {
            "default_project_id": self.id,
            "default_client_id": self.client_id.id,
            "default_client_file_id": self.client_file_id.id if "client_file_id" in self._fields else False,
            "default_engagement_id": self.engagement_letter_id.id,
            "default_employee_id": self.lawyer_id.id,
        }

    def _ensure_service_creation(self, service_type):
        self.ensure_one()
        self._ensure_legal_manager()
        if not self.id:
            raise UserError(_("Cannot create service without project."))
        if not self._allows_legal_service(service_type):
            raise UserError(_("This project service type does not allow this service record."))
        if service_type == "litigation" and not self.litigation_degree_ids:
            raise UserError(_("Select at least one litigation degree before creating a litigation case."))
        return True

    def action_create_litigation_case(self):
        self._ensure_service_creation("litigation")
        degree = self.litigation_degree_ids[:1]
        context = self._service_context()
        context.update(
            {
                "default_client_ids": self.client_id.ids,
                "default_litigation_degree_id": degree.id,
                "default_litigation_level_id": degree.level_id.id if degree.level_id else False,
                "default_litigation_flow": "litigation",
                "default_name": self.name,
                "default_name2": self.name,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Litigation Case"),
            "res_model": "qlk.case",
            "view_mode": "form",
            "target": "current",
            "context": context,
        }

    def _notify_project_created(self):
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for project in self:
            partners = (project.lawyer_id.user_id | project.responsible_user_ids).mapped("partner_id")
            body = _("Project %(project)s has been created for %(client)s.") % {
                "project": project.display_name,
                "client": project.client_id.display_name,
            }
            if partners:
                project.message_subscribe(partner_ids=partners.ids, subtype_ids=None)
                project.message_post(body=body, partner_ids=partners.ids)
            else:
                project.message_post(body=body)
            if activity_type:
                for user in (project.lawyer_id.user_id | project.responsible_user_ids).filtered("active"):
                    project.activity_schedule(
                        activity_type_id=activity_type.id,
                        user_id=user.id,
                        summary=_("New legal project"),
                        note=body,
                    )

    def _notify_hours_threshold(self, previous_remaining=None):
        activity_type = self.env.ref("mail.mail_activity_data_warning", raise_if_not_found=False) or self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        for project in self:
            if project.hours_state == "normal":
                continue
            if previous_remaining and previous_remaining.get(project.id, 0.0) < 0 and project.remaining_hours < 0:
                continue
            recipients = (project.lawyer_id.user_id | project.responsible_user_ids).filtered("active")
            message = (
                _("Project %(project)s exceeded planned hours by %(hours).2f hours.")
                if project.hours_state == "danger"
                else _("Project %(project)s is close to consuming all planned hours.")
            ) % {"project": project.display_name, "hours": project.overconsumed_hours}
            project.message_post(body=message, partner_ids=recipients.mapped("partner_id").ids)
            if activity_type:
                for user in recipients:
                    project.activity_schedule(
                        activity_type_id=activity_type.id,
                        user_id=user.id,
                        summary=_("Project hours warning"),
                        note=message,
                    )

    def action_create_corporate(self):
        self._ensure_service_creation("corporate")
        if not self.lawyer_id:
            raise UserError(_("Assign a lawyer before creating a corporate record."))
        record = self.env["qlk.corporate.case"].create(
            {
                "name": self.name,
                "project_id": self.id,
                "client_file_id": self.client_file_id.id,
                "client_id": self.client_id.id,
                "engagement_id": self.engagement_letter_id.id,
                "responsible_employee_id": self.lawyer_id.id,
            }
        )
        return self._open_record("qlk.corporate.case", record, _("Corporate"))

    def action_create_arbitration(self):
        self._ensure_service_creation("arbitration")
        record = self.env["qlk.arbitration.case"].create(
            {
                "name": self.name,
                "project_id": self.id,
                "client_file_id": self.client_file_id.id,
                "claimant_id": self.client_id.id,
                "engagement_id": self.engagement_letter_id.id,
                "responsible_employee_id": self.lawyer_id.id,
            }
        )
        return self._open_record("qlk.arbitration.case", record, _("Arbitration"))

    def action_create_pre_litigation(self):
        self._ensure_service_creation("pre_litigation")
        record = self.env["qlk.pre.litigation"].create(
            {
                "name": self.name,
                "project_id": self.id,
                "client_file_id": self.client_file_id.id,
                "client_id": self.client_id.id,
                "engagement_id": self.engagement_letter_id.id,
                "lawyer_employee_id": self.lawyer_id.id,
                "subject": self.name,
            }
        )
        return self._open_record("qlk.pre.litigation", record, _("Pre-Litigation"))

    def _open_record(self, model_name, record, title):
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_name,
            "res_id": record.id,
            "view_mode": "form",
            "target": "current",
        }

    def _open_related(self, model_name, title):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_name,
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id},
        }

    def action_open_cases(self):
        return self._open_related("qlk.case", _("Cases"))

    def action_open_project_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tasks"),
            "res_model": "project.task",
            "view_mode": "list,form",
            "domain": [("qlk_project_id", "=", self.id)],
            "context": {
                "default_partner_id": self.client_id.id,
                "qlk_require_case_id": True,
            },
        }

    def action_open_project_timesheets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Timesheets"),
            "res_model": "account.analytic.line",
            "view_mode": "list,form",
            "domain": [("task_id.qlk_project_id", "=", self.id)],
            "context": {"default_partner_id": self.client_id.id},
        }

    def action_open_corporate(self):
        return self._open_related("qlk.corporate.case", _("Corporate"))

    def action_open_arbitration(self):
        return self._open_related("qlk.arbitration.case", _("Arbitration"))

    def action_open_pre_litigation(self):
        return self._open_related("qlk.pre.litigation", _("Pre-Litigation"))


class BDEngagementLetter(models.Model):
    _inherit = "bd.engagement.letter"

    project_id = fields.Many2one(
        "qlk.project",
        string="Project",
        copy=False,
        ondelete="set null",
        tracking=True,
        domain=[],
    )

    def action_create_project(self):
        raise UserError(_("Projects must be created from the related Client File."))


class QlkTask(models.Model):
    _inherit = "qlk.task"

    department = fields.Selection(
        selection_add=[
            ("pre_litigation", "Pre-Litigation"),
            ("arbitration", "Arbitration"),
        ],
        ondelete={
            "pre_litigation": "set default",
            "arbitration": "set default",
        },
    )
    project_id = fields.Many2one("qlk.project", string="Project", ondelete="set null", index=True)
    client_file_id = fields.Many2one("qlk.client.file", string="Client File", related="project_id.client_file_id", store=True, readonly=True)
    client_id = fields.Many2one("res.partner", string="Client", related="project_id.client_id", store=True, readonly=True)
    pre_litigation_id = fields.Many2one("qlk.pre.litigation", string="Pre-Litigation", ondelete="set null", index=True)
    corporate_case_id = fields.Many2one("qlk.corporate.case", string="Corporate", ondelete="set null", index=True)
    arbitration_case_id = fields.Many2one("qlk.arbitration.case", string="Arbitration", ondelete="set null", index=True)
    planned_hours = fields.Float(string="Planned Hours", related="required_hours", store=True, readonly=False)
    consumed_hours = fields.Float(string="Consumed Hours", compute="_compute_task_hours", store=True)
    remaining_hours = fields.Float(string="Remaining Hours", compute="_compute_task_hours", store=True)

    @api.depends("planned_hours", "hours_spent")
    def _compute_task_hours(self):
        for task in self:
            task.consumed_hours = task.hours_spent or 0.0
            task.remaining_hours = (task.planned_hours or 0.0) - task.consumed_hours

    @api.onchange("project_id")
    def _onchange_project_id(self):
        for task in self:
            if task.project_id:
                task.partner_id = task.project_id.client_id.id
                task.engagement_id = task.project_id.engagement_letter_id.id
                if task.project_id.lawyer_id and not task.employee_id:
                    task.employee_id = task.project_id.lawyer_id.id

    def _apply_project_defaults(self, vals):
        project = self.env["qlk.project"].browse(vals.get("project_id"))
        if not project.exists():
            return vals
        vals.setdefault("partner_id", project.client_id.id)
        vals.setdefault("engagement_id", project.engagement_letter_id.id)
        vals.setdefault("employee_id", project.lawyer_id.id)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_project_defaults(vals)
        records = super().create(vals_list)
        records.mapped("project_id")._notify_hours_threshold()
        return records

    def write(self, vals):
        previous_projects = self.mapped("project_id")
        result = super().write(vals)
        if {"project_id", "hours_spent", "approval_state", "required_hours", "planned_hours"}.intersection(vals):
            (previous_projects | self.mapped("project_id"))._notify_hours_threshold()
        return result


class QlkCase(models.Model):
    _inherit = "qlk.case"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="restrict", index=True, tracking=True)
    planned_hours = fields.Float(string="Planned Hours", related="project_id.planned_hours", readonly=True)
    consumed_hours = fields.Float(string="Consumed Hours", compute="_compute_service_hours")
    remaining_hours = fields.Float(string="Remaining Hours", compute="_compute_service_hours")

    @api.depends("planned_hours", "case_hours")
    def _compute_service_hours(self):
        for record in self:
            record.consumed_hours = record.case_hours or 0.0
            record.remaining_hours = (record.planned_hours or 0.0) - record.consumed_hours

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                raise ValidationError(_("Cannot create service without project."))
            if vals.get("project_id"):
                self.env["qlk.project"]._ensure_legal_manager()
        return super().create(vals_list)


class CorporateCase(models.Model):
    _inherit = "qlk.corporate.case"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="restrict", index=True, tracking=True)
    planned_hours = fields.Float(string="Planned Hours", related="project_id.planned_hours", readonly=True)
    consumed_hours = fields.Float(string="Consumed Hours", compute="_compute_service_hours")
    remaining_hours = fields.Float(string="Remaining Hours", compute="_compute_service_hours")

    @api.depends("planned_hours", "actual_hours_total")
    def _compute_service_hours(self):
        for record in self:
            record.consumed_hours = record.actual_hours_total or 0.0
            record.remaining_hours = (record.planned_hours or 0.0) - record.consumed_hours

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                raise ValidationError(_("Cannot create service without project."))
            if vals.get("project_id"):
                self.env["qlk.project"]._ensure_legal_manager()
        return super().create(vals_list)


class ArbitrationCase(models.Model):
    _inherit = "qlk.arbitration.case"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="restrict", index=True, tracking=True)
    planned_hours = fields.Float(string="Planned Hours", related="project_id.planned_hours", readonly=True)
    consumed_hours = fields.Float(string="Consumed Hours", compute="_compute_service_hours")
    remaining_hours = fields.Float(string="Remaining Hours", compute="_compute_service_hours")

    @api.depends("planned_hours", "actual_hours_total")
    def _compute_service_hours(self):
        for record in self:
            record.consumed_hours = record.actual_hours_total or 0.0
            record.remaining_hours = (record.planned_hours or 0.0) - record.consumed_hours

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                raise ValidationError(_("Cannot create service without project."))
            if vals.get("project_id"):
                self.env["qlk.project"]._ensure_legal_manager()
        return super().create(vals_list)


class PreLitigation(models.Model):
    _inherit = "qlk.pre.litigation"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="restrict", index=True, tracking=True)
    planned_hours = fields.Float(string="Planned Hours", related="project_id.planned_hours", readonly=True)
    consumed_hours = fields.Float(string="Consumed Hours", compute="_compute_service_hours")
    remaining_hours = fields.Float(string="Remaining Hours", compute="_compute_service_hours")

    @api.depends("planned_hours", "hours_used")
    def _compute_service_hours(self):
        for record in self:
            record.consumed_hours = record.hours_used or 0.0
            record.remaining_hours = (record.planned_hours or 0.0) - record.consumed_hours

    @api.model
    def create(self, vals):
        if not vals.get("project_id"):
            raise ValidationError(_("Cannot create service without project."))
        if vals.get("project_id"):
            self.env["qlk.project"]._ensure_legal_manager()
        return super().create(vals)
