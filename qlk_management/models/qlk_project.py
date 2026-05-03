# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command


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
        required=True,
        tracking=True,
    )

    contract_type = fields.Selection(selection=CONTRACT_TYPE_SELECTION, string="Contract Type", tracking=True)
    billing_type = fields.Selection(selection=BILLING_TYPE_SELECTION, string="Billing Type", tracking=True)
    agreed_hours = fields.Float(string="Agreed Hours", tracking=True)
    total_hours = fields.Float(string="Total Hours", tracking=True)
    start_date = fields.Date(string="Start Date", tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
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

    planned_hours = fields.Float(string="Planned Hours", tracking=True)
    manual_consumed_hours = fields.Float(string="Manual Consumed Hours", tracking=True)
    consumed_hours = fields.Float(string="Consumed Hours", compute="_compute_hours", store=True)
    remaining_hours = fields.Float(string="Remaining Hours", compute="_compute_hours", store=True)

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
    case_ids = fields.One2many("qlk.case", "project_id", string="Cases")
    corporate_case_ids = fields.One2many("qlk.corporate.case", "project_id", string="Corporate")
    arbitration_case_ids = fields.One2many("qlk.arbitration.case", "project_id", string="Arbitration")
    pre_litigation_ids = fields.One2many("qlk.pre.litigation", "project_id", string="Pre-Litigation")
    case_count = fields.Integer(string="Cases", compute="_compute_service_counts")
    corporate_count = fields.Integer(string="Corporate", compute="_compute_service_counts")
    arbitration_count = fields.Integer(string="Arbitration", compute="_compute_service_counts")
    pre_litigation_count = fields.Integer(string="Pre-Litigation", compute="_compute_service_counts")
    task_count = fields.Integer(string="Tasks", compute="_compute_task_count")

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
        for project in self:
            if project.service_code or not project.client_id or not project.service_type:
                continue
            client_code = project.client_code or project.client_id._get_client_code()
            service_code = project._build_service_code(client_code, project.service_type)
            if service_code:
                project.with_context(
                    mail_create_nosubscribe=True,
                    mail_auto_subscribe_no_notify=True,
                    mail_notrack=True,
                ).write({"service_code": service_code})
        return True

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
    )
    def _compute_hours(self):
        for project in self:
            consumed = (project.manual_consumed_hours or 0.0) + sum(project.case_ids.mapped("case_hours"))
            project.consumed_hours = consumed
            project.remaining_hours = (project.planned_hours or 0.0) - consumed

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
            project.task_count = len(project.project_task_ids)

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
            if vals.get("engagement_letter_id"):
                existing = self.search([("engagement_letter_id", "=", vals["engagement_letter_id"])], limit=1)
                if existing:
                    raise ValidationError(_("A project already exists for this engagement letter."))
            vals.setdefault("planned_hours", vals.get("agreed_hours") or 0.0)
            if not vals.get("service_code") and vals.get("client_id") and vals.get("service_type"):
                client = self.env["res.partner"].browse(vals["client_id"])
                client_code = client._get_client_code()
                vals["service_code"] = self._build_service_code(client_code, vals["service_type"])
        projects = super(
            QlkProject,
            self.with_context(
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
            ),
        ).create(vals_list)
        projects._ensure_service_code()
        return projects

    def write(self, vals):
        if any(field in vals for field in ("client_id", "service_type", "engagement_letter_id")):
            self._ensure_legal_manager()
        return super().write(vals)

    @api.constrains("client_id", "service_type", "litigation_degree_ids")
    def _check_project_rules(self):
        for project in self:
            if not project.client_id:
                raise ValidationError(_("Cannot create project without client."))
            if project.service_type == "litigation" and not project.litigation_degree_ids:
                raise ValidationError(_("Litigation degree is required for litigation projects."))

    def _service_context(self):
        self.ensure_one()
        self._ensure_service_code()
        return {
            "default_project_id": self.id,
            "default_client_id": self.client_id.id,
            "default_engagement_id": self.engagement_letter_id.id,
            "default_employee_id": self.lawyer_id.id,
            "default_service_code": self.service_code,
        }

    def _ensure_service_creation(self, service_type):
        self.ensure_one()
        self._ensure_legal_manager()
        if not self.id:
            raise UserError(_("Cannot create service without project."))
        if self.service_type != service_type:
            raise UserError(_("This project service type does not allow this service record."))
        if service_type == "litigation" and not self.litigation_degree_ids:
            raise UserError(_("Select at least one litigation degree before creating a litigation case."))
        self._ensure_service_code()
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

    def action_create_corporate(self):
        self._ensure_service_creation("corporate")
        if not self.lawyer_id:
            raise UserError(_("Assign a lawyer before creating a corporate record."))
        record = self.env["qlk.corporate.case"].create(
            {
                "name": self.name,
                "project_id": self.id,
                "client_id": self.client_id.id,
                "engagement_id": self.engagement_letter_id.id,
                "responsible_employee_id": self.lawyer_id.id,
                "service_code": self.service_code,
            }
        )
        return self._open_record("qlk.corporate.case", record, _("Corporate"))

    def action_create_arbitration(self):
        self._ensure_service_creation("arbitration")
        record = self.env["qlk.arbitration.case"].create(
            {
                "name": self.name,
                "project_id": self.id,
                "claimant_id": self.client_id.id,
                "engagement_id": self.engagement_letter_id.id,
                "responsible_employee_id": self.lawyer_id.id,
                "service_code": self.service_code,
            }
        )
        return self._open_record("qlk.arbitration.case", record, _("Arbitration"))

    def action_create_pre_litigation(self):
        self._ensure_service_creation("pre_litigation")
        record = self.env["qlk.pre.litigation"].create(
            {
                "name": self.name,
                "project_id": self.id,
                "client_id": self.client_id.id,
                "engagement_id": self.engagement_letter_id.id,
                "lawyer_employee_id": self.lawyer_id.id,
                "subject": self.name,
                "service_code": self.service_code,
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
        self.ensure_one()
        self.env["qlk.project"]._ensure_legal_manager()
        if not self.partner_id:
            raise UserError(_("Please select a client before creating a project."))
        if self.project_id:
            raise UserError(_("A project already exists for this engagement letter."))
        existing_project = self.env["qlk.project"].search([("engagement_letter_id", "=", self.id)], limit=1)
        if existing_project:
            self.project_id = existing_project.id
            raise UserError(_("A project already exists for this engagement letter."))
        if self.service_type == "mixed":
            raise UserError(_("Select one specific service type before creating a project."))

        vals = {
            "name": self.code or self.reference or _("Engagement Project"),
            "client_id": self.partner_id.id,
            "engagement_letter_id": self.id,
            "lawyer_id": self.lawyer_employee_id.id,
            "service_type": self.service_type,
            "contract_type": self.contract_type,
            "billing_type": self.billing_type,
            "agreed_hours": self.agreed_hours,
            "planned_hours": self.agreed_hours,
            "total_hours": self.total_hours_used,
            "start_date": self.year_start_date,
            "end_date": self.year_end_date,
            "description": self.description or self.services_description,
            "scope_details": self.scope_of_work,
        }
        if self.service_type == "litigation" and self.litigation_degree_ids:
            vals["litigation_degree_ids"] = [Command.set(self.litigation_degree_ids.ids)]
        project = self.env["qlk.project"].with_context(
            mail_create_nosubscribe=True,
            mail_auto_subscribe_no_notify=True,
        ).create(vals)
        self.with_context(
            mail_create_nosubscribe=True,
            mail_auto_subscribe_no_notify=True,
        ).write({"project_id": project.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Project"),
            "res_model": "qlk.project",
            "res_id": project.id,
            "view_mode": "form",
            "target": "current",
        }


class QlkTask(models.Model):
    _inherit = "qlk.task"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="set null", index=True)


class QlkCase(models.Model):
    _inherit = "qlk.case"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="restrict", index=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                raise ValidationError(_("Cannot create service without project."))
            self.env["qlk.project"]._ensure_legal_manager()
        return super().create(vals_list)


class CorporateCase(models.Model):
    _inherit = "qlk.corporate.case"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="restrict", index=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                raise ValidationError(_("Cannot create service without project."))
            self.env["qlk.project"]._ensure_legal_manager()
        return super().create(vals_list)


class ArbitrationCase(models.Model):
    _inherit = "qlk.arbitration.case"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="restrict", index=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                raise ValidationError(_("Cannot create service without project."))
            self.env["qlk.project"]._ensure_legal_manager()
        return super().create(vals_list)


class PreLitigation(models.Model):
    _inherit = "qlk.pre.litigation"

    project_id = fields.Many2one("qlk.project", string="Project", ondelete="restrict", index=True, tracking=True)

    @api.model
    def create(self, vals):
        if not vals.get("project_id"):
            raise ValidationError(_("Cannot create service without project."))
        self.env["qlk.project"]._ensure_legal_manager()
        return super().create(vals)
