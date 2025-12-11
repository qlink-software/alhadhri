# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError, ValidationError

LITIGATION_WORKFLOW_TEMPLATE = [
    {"key": "translation", "name": "Translation of Documents", "sequence": 5},
    {"key": "draft_memo", "name": "Drafting the Memo", "sequence": 10},
    {"key": "approval_draft", "name": "Approval of the Draft", "sequence": 20},
    {"key": "client_portal", "name": "Client Approval via Portal", "sequence": 30},
    {"key": "signature_stamp", "name": "Signature & Stamp", "sequence": 40},
    {"key": "registration", "name": "Registration", "sequence": 50},
    {"key": "claim_correction", "name": "Claim Correction", "sequence": 60},
    {"key": "fee_payment", "name": "Fee Payment", "sequence": 70},
]


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
    # ------------------------------------------------------------------------------
    # نوع المشروع: تقاضي / تحكيم / شركات لتحديد المنطق التلقائي والمراحل المرتبطة.
    # ------------------------------------------------------------------------------
    project_type = fields.Selection(
        selection=[
            ("litigation", "Litigation Case"),
            ("arbitration", "Arbitration Case"),
            ("corporate", "Corporate Matter"),
        ],
        string="Project Type",
        required=True,
        default="litigation",
        tracking=True,
    )
    # ------------------------------------------------------------------------------
    # إذا اختار المستخدم project_type = 'litigation' يجب أن نحدد ما إذا كان Pre أو Case.
    # ------------------------------------------------------------------------------
    litigation_stage = fields.Selection(
        selection=[
            ("pre", "Pre-Litigation"),
            ("court", "Litigation Case"),
        ],
        string="Litigation Stage",
        default="court",
        tracking=True,
        help="حدد ما إذا كان المشروع قبل رفع الدعوى أو مرتبط بدعوى فعلية.",
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
    case_id = fields.Many2one("qlk.case", string="Linked Court Case", tracking=True, ondelete="set null")
    # ------------------------------------------------------------------------------
    # كود القضية (Litigation Project Code)
    # الصيغة: ClientCode/Lxxx-Stage/Code
    # أمثلة:
    # 256/L001/F
    # 256/L001-1/A
    # ------------------------------------------------------------------------------
    litigation_case_number = fields.Integer(string="Case Number", copy=False, tracking=True)
    litigation_stage_code = fields.Selection(
        selection=[
            ("F", "First Instance"),
            ("A", "Appeal"),
            ("CA", "Cassation"),
            ("E", "Enforcement"),
        ],
        string="Stage Code",
        default="F",
        tracking=True,
        help="Stage label appended to the litigation project code (F/A/CA/E).",
    )
    litigation_stage_iteration = fields.Integer(
        string="Stage Iteration",
        default=0,
        copy=False,
        tracking=True,
        help="Sequential index for repeated stages (e.g., re-opened appeals).",
    )
    litigation_court_id = fields.Many2one(
        "qlk.casegroup", string="Court", tracking=True, help="Court handling the litigation."
    )
    litigation_case_type_id = fields.Many2one(
        "qlk.secondcategory", string="Case Type", tracking=True, help="Type/category of the lawsuit."
    )
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
    project_scope = fields.Text(string="Project Scope")
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
    translation_task_id = fields.Many2one(
        "qlk.task",
        string="Translation Subtask",
        readonly=True,
        copy=False,
        help="Automatically created translation task for pre-litigation workflows.",
    )
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
    stage_line_ids = fields.One2many(
        "qlk.project.stage.line",
        "project_id",
        string="Workflow Stage Lines",
    )
    pre_litigation_id = fields.Many2one(
        "qlk.pre.litigation",
        string="Pre-Litigation Workflow",
        tracking=True,
    )
    stage_id = fields.Many2one(
        "qlk.project.stage",
        string="Workflow Stage",
        compute="_compute_stage_id",
        store=False,
        help="Virtual field exposing the first workflow stage line (if any) for dashboards.",
    )
    client_document_ids = fields.One2many(
        related="client_id.client_document_ids",
        string="Client Documents",
        readonly=True,
    )

    def _compute_stage_id(self):
        for project in self:
            stage_line = project.stage_line_ids[:1]
            project.stage_id = stage_line.stage_id if stage_line else False
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
        if self.department and not self.project_type:
            mapped_type = {
                "litigation": "litigation",
                "corporate": "corporate",
                "arbitration": "arbitration",
            }.get(self.department)
            if mapped_type:
                self.project_type = mapped_type

    @api.onchange("project_type")
    def _onchange_project_type(self):
        """Synchronize department and litigation stage whenever the type changes."""
        for project in self:
            project._apply_project_type_logic()

    @api.onchange("litigation_stage")
    def _onchange_litigation_stage(self):
        """Ensure the stage code/iteration follow the selected stage."""
        for project in self:
            if project.litigation_stage == "pre":
                project.litigation_stage_code = False
                project.litigation_stage_iteration = 0
            elif project.litigation_stage == "court":
                project.litigation_stage_code = project.litigation_stage_code or "F"
                project.litigation_stage_iteration = project.litigation_stage_iteration or 0

    @api.onchange("case_id")
    def _onchange_case_details(self):
        for project in self:
            case = project.case_id
            if not case:
                continue
            if not project.litigation_court_id:
                project.litigation_court_id = case.case_group
            if not project.litigation_case_type_id:
                project.litigation_case_type_id = case.second_category
            if project.project_type == "litigation" and not project.litigation_stage_code:
                project.litigation_stage_code = "F"

    @api.depends("client_id")
    def _compute_client_code(self):
        for project in self:
            code = ""
            if project.client_id:
                code = project.client_id.ref or f"{project.client_id.id:03d}"
            project.client_code = code or ""

    @api.depends(
        "case_sequence",
        "department",
        "client_code",
        "project_type",
        "litigation_case_number",
        "litigation_stage_code",
        "litigation_stage_iteration",
    )
    def _compute_code(self):
        for project in self:
            if project.project_type == "litigation":
                client_code = project.client_code or "PRJ"
                case_number = project.litigation_case_number or project.case_sequence or 1
                sequence_chunk = f"L{case_number:03d}"
                if project.litigation_stage_iteration:
                    sequence_chunk += f"-{project.litigation_stage_iteration}"
                code = f"{client_code}/{sequence_chunk}"
                if project.litigation_stage_code:
                    code = f"{code}/{project.litigation_stage_code}"
                project.code = code
            else:
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

    # ------------------------------------------------------------------------------
    # تطبيق منطق نوع المشروع لضبط القسم ومرحلة التقاضي بحسب الاختيار.
    # ------------------------------------------------------------------------------
    def _apply_project_type_logic(self):
        type_to_department = {
            "litigation": "litigation",
            "corporate": "corporate",
            "arbitration": "arbitration",
        }
        for project in self:
            project_type = project.project_type
            if not project_type:
                continue
            if type_to_department.get(project_type):
                project.department = type_to_department[project_type]
            if project_type == "litigation":
                project.litigation_stage = project.litigation_stage or "court"
            else:
                project.litigation_stage = False

    # ------------------------------------------------------------------------------
    # تجهيز القيم القادمة من الواجهة حسب نوع المشروع لضمان تماسك الحقول.
    # ------------------------------------------------------------------------------
    @api.model
    def _prepare_project_type_values(self, vals):
        vals = dict(vals)
        project_type = vals.get("project_type")
        if not project_type:
            return vals
        type_to_department = {
            "litigation": "litigation",
            "corporate": "corporate",
            "arbitration": "arbitration",
        }
        vals.setdefault("department", type_to_department.get(project_type, "litigation"))
        if project_type == "litigation":
            vals.setdefault("litigation_stage", "court")
            vals.setdefault("litigation_stage_code", "F")
            vals.setdefault("litigation_stage_iteration", 0)
        else:
            vals["litigation_stage"] = False
            vals["litigation_stage_code"] = False
            vals["litigation_stage_iteration"] = 0
        return vals

    # ------------------------------------------------------------------------------
    # تحديد رقم القضية التالي لكل عميل في مشاريع التقاضي.
    # ------------------------------------------------------------------------------
    def _next_litigation_case_number(self, client_id):
        domain = [("client_id", "=", client_id), ("project_type", "=", "litigation")]
        latest = self.search(domain, order="litigation_case_number desc", limit=1)
        return (latest.litigation_case_number or 0) + 1

    # ------------------------------------------------------------------------------
    # يستخدم عند الكتابة للتأكد من أن المشاريع الجديدة حصلت على أرقام قضايا صحيحة.
    # ------------------------------------------------------------------------------
    def _assign_missing_litigation_numbers(self):
        for project in self:
            if project.project_type != "litigation" or not project.client_id:
                continue
            if not project.litigation_case_number:
                next_number = self._next_litigation_case_number(project.client_id.id)
                super(QlkProject, project).write(
                    {
                        "litigation_case_number": next_number,
                        "case_sequence": project.case_sequence or next_number,
                    }
                )
            elif not project.case_sequence:
                super(QlkProject, project).write({"case_sequence": project.litigation_case_number})

    # ------------------------------------------------------------------------------
    # ضمان تجهيز مهام ومراحل التقاضي (Subtask + Workflow Stages).
    # ------------------------------------------------------------------------------
    def _ensure_litigation_workflow(self):
        for project in self:
            if project.project_type == "litigation":
                project._ensure_litigation_stage_lines()
                if project.litigation_stage == "pre":
                    project._ensure_translation_subtask()
            else:
                if project.stage_line_ids:
                    project.stage_line_ids.unlink()
                if project.translation_task_id:
                    project.translation_task_id = False

    # ------------------------------------------------------------------------------
    # إنشاء Subtask الترجمة تلقائياً مع الإشعارات.
    # ------------------------------------------------------------------------------
    def _ensure_translation_subtask(self):
        self.ensure_one()
        if self.translation_task_id:
            return
        if not self.assigned_employee_ids:
            raise UserError(_("Assign at least one lawyer before generating the translation subtask."))
        employee = self.assigned_employee_ids[:1]
        company = self.company_id or self.env.company
        Task = self.env["qlk.task"]
        task_vals = {
            "name": _("Translation of Documents"),
            "description": _(
                "Automatic translation subtask generated for project %(code)s.\n"
                "- Upload documents that require translation.\n"
                "- Notify the responsible lawyer after uploading."
            )
            % {"code": self.display_name},
            "department": "litigation",
            "litigation_phase": "pre",
            "project_id": self.id,
            "employee_id": employee.id,
            "company_id": company.id,
            "hours_spent": 1.0,
            "date_start": fields.Date.context_today(self),
            "approval_state": "draft",
        }
        task = Task.create(task_vals)
        self.translation_task_id = task.id
        partners = employee.mapped("user_id.partner_id")
        if partners:
            task.message_subscribe(partner_ids=partners.ids)
        task.message_post(body=_("Translation task created automatically from %s.") % self.display_name)
        self.message_post(
            body=_("Translation task %(task)s created and assigned to %(user)s.")
            % {"task": task.display_name, "user": employee.name}
        )
        stage_line = self.stage_line_ids.filtered(lambda line: line.stage_key == "translation")[:1]
        if stage_line:
            stage_line.task_id = task.id

    # ------------------------------------------------------------------------------
    # إنشاء مراحل العمل الافتراضية لمشاريع التقاضي.
    # ------------------------------------------------------------------------------
    def _ensure_litigation_stage_lines(self):
        for project in self:
            if project.project_type != "litigation":
                continue
            existing_keys = set(project.stage_line_ids.mapped("stage_key"))
            commands = []
            for template in LITIGATION_WORKFLOW_TEMPLATE:
                if template["key"] in existing_keys:
                    continue
                commands.append(
                    (
                        0,
                        0,
                        {
                            "name": template["name"],
                            "stage_key": template["key"],
                            "sequence": template["sequence"],
                        },
                    )
                )
            if commands:
                project.stage_line_ids = commands

    # ------------------------------------------------------------------------------
    # إنشاء القضايا المرتبطة تلقائياً حسب نوع المشروع ومراحله.
    # ------------------------------------------------------------------------------
    def _auto_create_default_cases(self):
        Case = self.env.get("qlk.case")
        ArbitrationCase = self.env.get("qlk.arbitration.case")
        CorporateCase = self.env.get("qlk.corporate.case")
        for project in self:
            if project.project_type == "litigation":
                if project.litigation_stage == "court" and not project.case_id and Case:
                    case_vals = project._prepare_litigation_case_vals()
                    if case_vals:
                        case = Case.create(case_vals)
                        project.case_id = case.id
            elif project.project_type == "arbitration":
                if not project.arbitration_case_id and ArbitrationCase:
                    case_vals = project._prepare_arbitration_case_vals()
                    if case_vals:
                        case = ArbitrationCase.create(case_vals)
                        project.arbitration_case_id = case.id
            elif project.project_type == "corporate":
                if not project.corporate_case_id and CorporateCase:
                    case_vals = project._prepare_corporate_case_vals()
                    if case_vals:
                        case = CorporateCase.create(case_vals)
                        project.corporate_case_id = case.id

    # ------------------------------------------------------------------------------
    # تهيئة بيانات القضية الخاصة بالتقاضي بناءً على المشروع الحالي.
    # ------------------------------------------------------------------------------
    def _prepare_litigation_case_vals(self):
        self.ensure_one()
        if not self.client_id:
            return False
        lawyer = self._get_primary_employee()
        currency = self.company_id.currency_id
        case_name = self.client_id.display_name or self.name
        return {
            "name": case_name,
            "name2": self.code or case_name,
            "client_id": self.client_id.id,
            "employee_id": lawyer.id if lawyer else False,
            "company_id": self.company_id.id,
            "description": self.description,
            "client_capacity": self.client_capacity,
            "currency_id": currency.id if currency else False,
            "case_number": self.litigation_case_number,
            "litigation_flow": "litigation" if self.litigation_stage == "court" else "pre_litigation",
            "case_group": self.litigation_court_id.id if self.litigation_court_id else False,
            "second_category": self.litigation_case_type_id.id if self.litigation_case_type_id else False,
        }

    # ------------------------------------------------------------------------------
    # تهيئة بيانات قضية التحكيم.
    # ------------------------------------------------------------------------------
    def _prepare_arbitration_case_vals(self):
        self.ensure_one()
        if not self.client_id:
            return False
        lawyer = self._get_primary_employee()
        if not lawyer:
            return False
        return {
            "name": self.name,
            "case_number": self.code,
            "claimant_id": self.client_id.id,
            "responsible_employee_id": lawyer.id if lawyer else False,
            "project_id": self.id,
        }

    # ------------------------------------------------------------------------------
    # تهيئة بيانات قضية الشركات.
    # ------------------------------------------------------------------------------
    def _prepare_corporate_case_vals(self):
        self.ensure_one()
        if not self.client_id:
            return False
        lawyer = self._get_primary_employee()
        if not lawyer:
            return False
        return {
            "name": self.name,
            "client_id": self.client_id.id,
            "responsible_employee_id": lawyer.id,
            "project_id": self.id,
        }

    # ------------------------------------------------------------------------------
    # اختيار الموظف الأساسي (إما من الفريق المعين أو مالك المشروع).
    # ------------------------------------------------------------------------------
    def _get_primary_employee(self):
        self.ensure_one()
        employee = self.assigned_employee_ids[:1]
        if employee:
            return employee
        if self.owner_id:
            return self.env["hr.employee"].search([("user_id", "=", self.owner_id.id)], limit=1)
        return False

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE qlk_project
               SET project_type = department
             WHERE project_type IS NULL
            """
        )
        self.env.cr.execute(
            """
            UPDATE qlk_project
               SET litigation_stage = 'court'
             WHERE project_type = 'litigation' AND litigation_stage IS NULL
            """
        )
        self.env.cr.execute(
            """
            UPDATE qlk_project
               SET litigation_stage_code = 'F'
             WHERE project_type = 'litigation' AND litigation_stage = 'court' AND litigation_stage_code IS NULL
            """
        )

    def _prepare_project_type_values(self, vals):
        project_type = vals.get("project_type")
        if not project_type:
            return vals
        vals = dict(vals)
        type_to_department = {
            "litigation": "litigation",
            "corporate": "corporate",
            "arbitration": "arbitration",
        }
        vals.setdefault("department", type_to_department.get(project_type, "litigation"))
        if project_type == "litigation":
            vals.setdefault("litigation_stage", "court")
        else:
            vals["litigation_stage"] = False
        return vals

    @api.model
    def create(self, vals):
        prepared_vals = self._prepare_project_type_values(vals)
        project = super().create(prepared_vals)
        project._sync_case_metadata_from_case()
        return project

    def write(self, vals):
        write_vals = vals
        if "project_type" in vals:
            write_vals = self._prepare_project_type_values(vals)
        res = super().write(write_vals)
        if "case_id" in vals and not self.env.context.get("skip_case_sync"):
            self._sync_case_metadata_from_case()
        return res

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
            prepared = self._prepare_project_type_values(vals)
            department = prepared.get("department") or "litigation"
            self._validate_case_vals(prepared, department, is_create=True)
            client_id = prepared.get("client_id")
            if prepared.get("project_type") == "litigation" and client_id:
                if not prepared.get("litigation_case_number"):
                    next_number = self._next_litigation_case_number(client_id)
                    prepared["litigation_case_number"] = next_number
                prepared.setdefault("case_sequence", prepared.get("litigation_case_number"))
            elif client_id and not prepared.get("case_sequence"):
                prepared["case_sequence"] = self._next_case_sequence(client_id, department)
            res.append(prepared)

        projects = super().create(res)
        projects._auto_create_default_cases()
        projects._sync_case_project_link()
        projects._sync_case_metadata_from_case()
        projects._post_create_notifications()
        projects._ensure_litigation_workflow()
        return projects

    def write(self, vals):
        prepared_vals = self._prepare_project_type_values(vals) if "project_type" in vals else vals
        case_fields = tuple(self._department_case_field_map.values())
        old_corporate_cases = {project.id: project.corporate_case_id for project in self}
        old_arbitration_cases = {project.id: project.arbitration_case_id for project in self}

        if "department" in prepared_vals:
            new_department = prepared_vals["department"]
            if new_department == "litigation":
                if "corporate_case_id" not in prepared_vals:
                    prepared_vals["corporate_case_id"] = False
                if "arbitration_case_id" not in prepared_vals:
                    prepared_vals["arbitration_case_id"] = False
            elif new_department == "corporate":
                if "case_id" not in prepared_vals:
                    prepared_vals["case_id"] = False
                if "arbitration_case_id" not in prepared_vals:
                    prepared_vals["arbitration_case_id"] = False
            elif new_department == "arbitration":
                if "case_id" not in prepared_vals:
                    prepared_vals["case_id"] = False
                if "corporate_case_id" not in prepared_vals:
                    prepared_vals["corporate_case_id"] = False

        if any(field in prepared_vals for field in case_fields) or "department" in prepared_vals:
            for project in self:
                department = prepared_vals.get("department", project.department)
                self._validate_case_vals(prepared_vals, department, is_create=False)

        result = super().write(prepared_vals)
        if "assigned_employee_ids" in prepared_vals:
            self._notify_assignment_changes()

        self._assign_missing_litigation_numbers()

        triggers = set(prepared_vals.keys())
        if triggers.intersection(set(case_fields)) or "department" in triggers or "project_type" in triggers or "litigation_stage" in triggers:
            self._auto_create_default_cases()
            self._clear_stale_case_links(old_corporate_cases, old_arbitration_cases)
            self._sync_case_project_link()
            self._ensure_litigation_workflow()
            self._sync_case_metadata_from_case()
        return result

    def _sync_case_metadata_from_case(self):
        for project in self:
            case = project.case_id
            if not case:
                continue
            updates = {}
            if case.case_group and project.litigation_court_id != case.case_group:
                updates["litigation_court_id"] = case.case_group.id
            if case.second_category and project.litigation_case_type_id != case.second_category:
                updates["litigation_case_type_id"] = case.second_category.id
            if updates:
                project.with_context(skip_case_sync=True).write(updates)

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
        if self.project_type != "litigation":
            raise UserError(_("Only litigation projects can be transferred to a court case."))
        if self.case_id:
            raise UserError(_("This project is already linked to a litigation case."))
        if self.litigation_stage != "pre":
            raise UserError(_("Transfer to litigation is available once the project is in the pre-litigation stage."))
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
