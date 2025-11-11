# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError, ValidationError


class QlkProject(models.Model):
    _name = "qlk.project"
    _description = "Legal Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    _department_case_field_map = {
        "litigation": "case_id",
        "corporate": "corporate_case_id",
        "arbitration": "arbitration_case_id",
    }

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string="Project Code", compute="_compute_code", store=True, tracking=True)
    reference = fields.Char(string="Reference", copy=False, tracking=True)
    department = fields.Selection(
        selection=[
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
        ],
        required=True,
        default="litigation",
        tracking=True,
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
    client_capacity = fields.Char(string="Client Capacity", tracking=True)
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
    task_count = fields.Integer(
        string="Tasks",
        compute="_compute_task_hours",
        readonly=True,
    )
    deadline = fields.Date(string="Overall Deadline")
    color = fields.Integer(string="Color Index")
    transfer_ready = fields.Boolean(
        string="Ready to Transfer",
        help="Checked when all required stages are completed and case details can be submitted.",
    )
    corporate_case_id = fields.Many2one(
        "qlk.corporate.case",
        string="Corporate Case",
        tracking=True,
        ondelete="set null",
    )
    arbitration_case_id = fields.Many2one(
        "qlk.arbitration.case",
        string="Arbitration Case",
        tracking=True,
        ondelete="set null",
    )
    related_case_display = fields.Char(string="Related Matter", compute="_compute_related_case_display")
    client_document_ids = fields.One2many(
        related="client_id.client_document_ids",
        string="Client Documents",
        readonly=True,
    )
    client_document_warning = fields.Html(
        related="client_id.document_warning_message",
        string="Document Warning",
        readonly=True,
    )
    client_document_warning_required = fields.Boolean(
        related="client_id.document_warning_required",
        readonly=True,
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

    @api.onchange("department")
    def _onchange_department(self):
        if not self.department:
            return
        allowed_field = self._department_case_field_map.get(self.department)
        for field_name in self._department_case_field_map.values():
            if field_name != allowed_field:
                setattr(self, field_name, False)

    @api.onchange("engagement_id")
    def _onchange_engagement_id(self):
        if not self.engagement_id:
            return
        if not self.client_id:
            self.client_id = self.engagement_id.partner_id
        if self.engagement_id.client_capacity and not self.client_capacity:
            self.client_capacity = self.engagement_id.client_capacity

    @api.depends("client_id", "engagement_id.client_unique_code")
    def _compute_client_code(self):
        for project in self:
            code = project.engagement_id.client_unique_code
            if not code and project.client_id:
                code = project.client_id.ref or f"{project.client_id.id:03d}"
            project.client_code = code or ""

    @api.depends("case_sequence", "department", "client_code")
    def _compute_code(self):
        for project in self:
            client_code = project.client_code or "PRJ"
            sequence = project.case_sequence or 1
            department_prefix = {
                "litigation": "L",
                "corporate": "C",
                "arbitration": "A",
            }.get(project.department, "P")
            project.code = f"{client_code}/{department_prefix}{sequence:03d}"

    @api.depends("task_ids.approval_state", "task_ids.hours_spent", "task_ids.date_start")
    def _compute_task_hours(self):
        approved_states = {"approved"}
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for project in self:
            total = 0.0
            month_total = 0.0
            count = 0
            for task in project.task_ids:
                if task.approval_state in approved_states:
                    total += task.hours_spent
                    if task.date_start and task.date_start >= month_start:
                        month_total += task.hours_spent
                count += 1
            project.task_hours_total = total
            project.task_hours_month = month_total
            project.task_count = count

    def _get_department_label(self, department):
        department_field = self._fields["department"]
        selection = department_field.selection
        if callable(selection):
            selection = selection(self)
        selection_dict = dict(selection or [])
        if isinstance(department, str):
            return selection_dict.get(department, department.title())
        return selection_dict.get(department, department)

    def _ensure_client_documents_ready(self):
        for project in self:
            if not project.client_id:
                continue
            missing = project.client_id.get_missing_document_labels()
            if missing:
                raise UserError(
                    _(
                        "Client %(client)s is missing the following documents: %(docs)s. "
                        "Please attach them from the contact record before proceeding."
                    )
                    % {
                        "client": project.client_id.display_name,
                        "docs": ", ".join(missing),
                    }
                )

    def _validate_case_vals(self, vals, department, *, is_create=False):
        allowed_field = self._department_case_field_map.get(department)
        department_label = self._get_department_label(department)
        for field_name in self._department_case_field_map.values():
            if field_name == allowed_field:
                continue
            value = vals.get(field_name)
            if value:
                raise ValidationError(
                    _("%(field)s cannot be set on %(dept)s projects.") % {
                        "field": self._fields[field_name].string,
                        "dept": department_label,
                    }
                )
            if is_create and field_name not in vals:
                vals[field_name] = False

    @api.model_create_multi
    def create(self, vals_list):
        res = []
        for vals in vals_list:
            department = vals.get("department") or "litigation"
            self._validate_case_vals(vals, department, is_create=True)

            client_id = vals.get("client_id")
            engagement_id = vals.get("engagement_id")
            if engagement_id:
                engagement = self.env["qlk.engagement.letter"].browse(engagement_id)
                if not client_id and engagement.partner_id:
                    client_id = engagement.partner_id.id
                    vals["client_id"] = client_id
                if engagement.client_capacity and not vals.get("client_capacity"):
                    vals["client_capacity"] = engagement.client_capacity
            if client_id and not vals.get("case_sequence"):
                vals["case_sequence"] = self._next_case_sequence(client_id, vals.get("department"))

            res.append(vals)

        projects = super().create(res)
        projects._sync_case_project_link()
        projects._post_create_notifications()
        return projects

    def write(self, vals):
        case_fields = tuple(self._department_case_field_map.values())
        old_corporate_cases = {project.id: project.corporate_case_id for project in self}
        old_arbitration_cases = {project.id: project.arbitration_case_id for project in self}

        if "department" in vals:
            new_department = vals["department"]
            if new_department == "litigation":
                if "corporate_case_id" not in vals:
                    vals["corporate_case_id"] = False
                if "arbitration_case_id" not in vals:
                    vals["arbitration_case_id"] = False
            elif new_department == "corporate":
                if "case_id" not in vals:
                    vals["case_id"] = False
                if "arbitration_case_id" not in vals:
                    vals["arbitration_case_id"] = False
            elif new_department == "arbitration":
                if "case_id" not in vals:
                    vals["case_id"] = False
                if "corporate_case_id" not in vals:
                    vals["corporate_case_id"] = False

        if any(field in vals for field in case_fields) or "department" in vals:
            for project in self:
                department = vals.get("department", project.department)
                self._validate_case_vals(vals, department, is_create=False)

        result = super().write(vals)
        if "assigned_employee_ids" in vals:
            self._notify_assignment_changes()

        if any(key in vals for key in (*case_fields, "department")):
            self._clear_stale_case_links(old_corporate_cases, old_arbitration_cases)
            self._sync_case_project_link()
        return result

    def _clear_stale_case_links(self, old_corporate_cases, old_arbitration_cases):
        for project in self:
            old_corporate = old_corporate_cases.get(project.id)
            if old_corporate and old_corporate != project.corporate_case_id:
                if hasattr(old_corporate, "project_id") and old_corporate.project_id == project:
                    old_corporate.project_id = False
            old_arbitration = old_arbitration_cases.get(project.id)
            if old_arbitration and old_arbitration != project.arbitration_case_id:
                if hasattr(old_arbitration, "project_id") and old_arbitration.project_id == project:
                    old_arbitration.project_id = False

    def _sync_case_project_link(self):
        for project in self:
            corporate_case = project.corporate_case_id
            if corporate_case and hasattr(corporate_case, "project_id"):
                existing_project = corporate_case.project_id
                if existing_project and existing_project != project:
                    raise ValidationError(
                        _("%(case)s is already linked to project %(project)s.") % {
                            "case": corporate_case.display_name,
                            "project": existing_project.display_name,
                        }
                    )
                if existing_project != project:
                    corporate_case.project_id = project.id

            arbitration_case = project.arbitration_case_id
            if arbitration_case and hasattr(arbitration_case, "project_id"):
                existing_project = arbitration_case.project_id
                if existing_project and existing_project != project:
                    raise ValidationError(
                        _("%(case)s is already linked to project %(project)s.") % {
                            "case": arbitration_case.display_name,
                            "project": existing_project.display_name,
                        }
                    )
                if existing_project != project:
                    arbitration_case.project_id = project.id

    @api.constrains("department", "case_id", "corporate_case_id", "arbitration_case_id")
    def _check_department_case_alignment(self):
        all_fields = tuple(self._department_case_field_map.values())
        for project in self:
            linked_fields = [field for field in all_fields if getattr(project, field)]
            if len(linked_fields) > 1:
                raise ValidationError(_("Only one matter can be linked to a project at a time."))
            if not linked_fields:
                continue
            allowed_field = self._department_case_field_map.get(project.department)
            linked_field = linked_fields[0]
            if allowed_field and linked_field != allowed_field:
                raise ValidationError(
                    _("%(field)s does not match the %(dept)s department.") % {
                        "field": self._fields[linked_field].string,
                        "dept": self._get_department_label(project.department),
                    }
                )

    def _next_case_sequence(self, client_id, department):
        domain = [("client_id", "=", client_id), ("department", "=", department)]
        latest = self.search(domain, order="case_sequence desc", limit=1)
        return (latest.case_sequence or 0) + 1

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

    def action_open_log_hours(self):
        self.ensure_one()
        default_employee = (
            self.assigned_employee_ids[:1].id
            if self.assigned_employee_ids
            else self.env.user.employee_id.id
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "qlk.project.log.hours",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
                "default_department": self.department,
                "default_employee_id": default_employee,
            },
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
                "default_department": self.department,
                "search_default_group_month": 1,
            }
        )
        action["context"] = context
        action["domain"] = [("project_id", "=", self.id)]
        return action

    def action_view_hours(self):
        self.ensure_one()
        action = self.env.ref("qlk_project_management.action_qlk_project_hours").read()[0]
        action["domain"] = [
            ("project_id", "=", self.id),
            ("approval_state", "=", "approved"),
        ]
        context = action.get("context") or {}
        if isinstance(context, str):
            context = safe_eval(context)
        context.update({
            "default_project_id": self.id,
            "group_by": "assigned_user_id",
        })
        action["context"] = context
        return action

    @api.depends("department", "case_id", "corporate_case_id", "arbitration_case_id")
    def _compute_related_case_display(self):
        for project in self:
            if project.department == "litigation" and project.case_id:
                project.related_case_display = project.case_id.display_name
            elif project.department == "corporate" and project.corporate_case_id:
                project.related_case_display = project.corporate_case_id.display_name
            elif project.department == "arbitration" and project.arbitration_case_id:
                project.related_case_display = project.arbitration_case_id.display_name
            else:
                project.related_case_display = ""

    def action_open_related_case(self):
        self.ensure_one()
        if self.department == "litigation" and self.case_id:
            action = self.env.ref("qlk_law.act_open_qlk_case_view", raise_if_not_found=False)
            if action:
                result = action.read()[0]
                result["res_id"] = self.case_id.id
                result["view_mode"] = "form"
                result["views"] = [(False, "form")]
                context = result.get("context")
                if isinstance(context, str):
                    context = safe_eval(context)
                context = dict(context or {})
                context.setdefault("default_project_id", self.id)
                result["context"] = context
                return result
        elif self.department == "corporate" and self.corporate_case_id:
            action = self.env.ref("qlk_corporate.action_corporate_case", raise_if_not_found=False)
            if action:
                result = action.read()[0]
                result["res_id"] = self.corporate_case_id.id
                result["view_mode"] = "form"
                result["views"] = [(False, "form")]
                domain = result.get("domain")
                if isinstance(domain, str):
                    domain = safe_eval(domain)
                if not domain:
                    domain = []
                domain.append(("id", "=", self.corporate_case_id.id))
                result["domain"] = domain
                context = result.get("context")
                if isinstance(context, str):
                    context = safe_eval(context)
                context = dict(context or {})
                context.setdefault("default_project_id", self.id)
                result["context"] = context
                return result
        elif self.department == "arbitration" and self.arbitration_case_id:
            action = self.env.ref("qlk_arbitration.action_arbitration_case", raise_if_not_found=False)
            if action:
                result = action.read()[0]
                result["res_id"] = self.arbitration_case_id.id
                result["view_mode"] = "form"
                result["views"] = [(False, "form")]
                domain = result.get("domain")
                if isinstance(domain, str):
                    domain = safe_eval(domain)
                if not domain:
                    domain = []
                domain.append(("id", "=", self.arbitration_case_id.id))
                result["domain"] = domain
                context = result.get("context")
                if isinstance(context, str):
                    context = safe_eval(context)
                context = dict(context or {})
                context.setdefault("default_project_id", self.id)
                result["context"] = context
                return result
        raise UserError(_("No related case is linked to this project."))

    def _action_open_transfer_wizard(self, flow):
        self.ensure_one()
        if self.department != "litigation":
            raise UserError(_("Only litigation projects can be transferred to a court case."))
        if self.case_id:
            raise UserError(_("This project is already linked to a litigation case."))
        self._ensure_client_documents_ready()
        return {
            "type": "ir.actions.act_window",
            "res_model": "qlk.project.transfer.litigation",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
                "default_client_id": self.client_id.id,
                "default_assigned_employee_id": self.assigned_employee_ids[:1].id if self.assigned_employee_ids else False,
                "default_litigation_flow": flow,
            },
        }

    def action_transfer_to_litigation(self):
        return self._action_open_transfer_wizard(flow="litigation")

    def action_transfer_to_pre_litigation(self):
        return self._action_open_transfer_wizard(flow="pre_litigation")

    def action_transfer_to_corporate(self):
        self.ensure_one()
        if self.department != "corporate":
            raise UserError(_("Only corporate projects can be transferred to a corporate case."))
        if self.corporate_case_id:
            raise UserError(_("This project is already linked to a corporate case."))
        self._ensure_client_documents_ready()
        return {
            "type": "ir.actions.act_window",
            "res_model": "qlk.project.transfer.corporate",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
                "default_client_id": self.client_id.id,
                "default_case_name": self.name,
                "default_assigned_employee_id": self.assigned_employee_ids[:1].id if self.assigned_employee_ids else False,
            },
        }

    def action_transfer_to_arbitration(self):
        self.ensure_one()
        if self.department != "arbitration":
            raise UserError(_("Only arbitration projects can be transferred to an arbitration case."))
        if self.arbitration_case_id:
            raise UserError(_("This project is already linked to an arbitration case."))
        self._ensure_client_documents_ready()
        return {
            "type": "ir.actions.act_window",
            "res_model": "qlk.project.transfer.arbitration",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
                "default_client_id": self.client_id.id,
                "default_case_name": self.name,
                "default_claimant_id": self.client_id.id,
                "default_assigned_employee_id": self.assigned_employee_ids[:1].id if self.assigned_employee_ids else False,
            },
        }
