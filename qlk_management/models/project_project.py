# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

PROJECT_TYPE_SELECTION = [
    ("cm", "CM"),
    ("lm", "LM"),
    ("lc", "LC"),
    ("corporate", "Corporate"),
    ("litigation", "Litigation"),
    ("arbitration", "Arbitration"),
]

RETAINER_TYPE_SELECTION = [
    ("litigation", "Litigation"),
    ("corporate", "Corporate"),
    ("arbitration", "Arbitration"),
    ("litigation_corporate", "Litigation + Corporate"),
    ("management_corporate", "Management Corporate"),
    ("management_litigation", "Management Litigation"),
]

PROJECT_CONTRACT_TYPE_SELECTION = [
    ("hours", "Hours Based"),
    ("cases", "Case Based"),
    ("retainer", "Retainer"),
    ("lump_sum", "Lump Sum"),
    ("litigation", "Litigation"),
    ("corporate", "Corporate"),
    ("combined", "Combined"),
    ("arbitration", "Arbitration"),
]

LEGAL_SERVICE_TYPE_SELECTION = [
    ("litigation", "Litigation"),
    ("corporate", "Corporate"),
    ("arbitration", "Arbitration"),
    ("pre_litigation", "Pre-Litigation"),
]

LEGAL_SERVICE_CODE_PREFIX = {
    "litigation": "L",
    "arbitration": "A",
    "corporate": "C",
    "pre_litigation": "P",
}

LEGAL_MANAGER_GROUPS = (
    "qlk_management.group_bd_manager",
    "qlk_management.group_el_manager",
)


class ProjectProject(models.Model):
    _inherit = "project.project"

    # The standard project partner is used here as a lawyer selector in the legal workflow.
    partner_id = fields.Many2one("res.partner", domain=[("is_lawyer", "=", True)])
    cost_calculation_id = fields.Many2one("cost.calculation", string="Cost Calculation")
    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        index=True,
        tracking=True,
        domain="[('customer_rank', '>', 0)]",
    )
    client_mobile = fields.Char(string="Mobile", related="client_id.mobile", readonly=True)
    client_email = fields.Char(string="Email", related="client_id.email", readonly=True)
    client_qid_cr = fields.Char(string="QID / CR Number", compute="_compute_client_profile_fields")
    client_address = fields.Text(string="Address", compute="_compute_client_profile_fields")
    client_document_ids = fields.One2many(
        related="client_id.client_document_ids",
        string="Client Documents",
    )
    lawyer_id = fields.Many2one(
        "hr.employee",
        string="Lawyer",
        domain=[("user_id.partner_id.is_lawyer", "=", True)],
    )
    lawyer_hour_cost = fields.Float(string="Lawyer Hour Cost", compute="_compute_lawyer_costs", store=True)
    lawyer_hours = fields.Float(string="Lawyer Hours")
    lawyer_total_cost = fields.Float(string="Lawyer Total Cost", compute="_compute_totals", store=True)
    additional_project_cost = fields.Float(string="Additional Project Cost")
    total_cost_all = fields.Float(string="Total Cost", compute="_compute_totals", store=True)
    engagement_letter_id = fields.Many2one(
        "bd.engagement.letter",
        string="Engagement Letter",
        index=True,
        ondelete="set null",
    )
    contract_type = fields.Selection(
        selection=PROJECT_CONTRACT_TYPE_SELECTION,
        string="Contract Type",
        copy=False,
    )
    billing_type = fields.Selection(
        [("free", "Pro bono"), ("paid", "Paid")],
        string="Billing Type",
    )
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True)
    payment_state = fields.Selection(
        selection=[
            ("not_paid", "Not Paid"),
            ("in_payment", "In Payment"),
            ("paid", "Paid"),
            ("partial", "Partially Paid"),
            ("reversed", "Reversed"),
        ],
        string="Invoice Payment State",
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    code = fields.Char(string="Project Code", default="/", copy=False, readonly=True)
    client_code = fields.Char(string="Client Code", copy=False, readonly=True)
    service_type = fields.Selection(
        selection=LEGAL_SERVICE_TYPE_SELECTION,
        string="Service Type",
        copy=False,
        tracking=True,
    )
    service_code = fields.Char(
        string="Service Code",
        readonly=True,
        copy=False,
    )
    litigation_case_count = fields.Integer(string="Cases", compute="_compute_service_counts")
    corporate_case_count = fields.Integer(string="Corporate", compute="_compute_service_counts")
    arbitration_case_count = fields.Integer(string="Arbitration", compute="_compute_service_counts")
    pre_litigation_count = fields.Integer(string="Pre-Litigation", compute="_compute_service_counts")
    project_type = fields.Selection(
        selection=PROJECT_TYPE_SELECTION,
        string="Project Type",
        default="corporate",
    )
    retainer_type = fields.Selection(
        selection=RETAINER_TYPE_SELECTION,
        string="Services Type",
        default="corporate",
    )
    fee_structure = fields.Char(string="Fee Structure")
    payment_terms = fields.Char(string="Payment Terms")
    engagement_reference = fields.Char(string="Engagement Reference", readonly=True)
    legal_fee_amount = fields.Monetary(string="Legal Fees", currency_field="company_currency_id")
    is_mini_project = fields.Boolean(string="Mini Project")
    mini_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Completed"),
        ],
        string="Mini Project Stage",
        default="draft",
        copy=False,
    )
    mp_id = fields.Many2one("res.users", string="Mini Project Manager")
    bd_user_id = fields.Many2one("res.users", string="BD Owner")
    needs_translation = fields.Boolean(string="Needs Translation")
    translation_requested = fields.Boolean(string="Translation Notified", default=False, copy=False)
    lawyer_assigned = fields.Boolean(string="Lawyer Confirmed", default=False, copy=False)
    is_mp_user = fields.Boolean(compute="_compute_user_permissions", string="Is Current MP")

    def _build_service_code(self, client_code, service_type):
        if not client_code or not service_type:
            return False
        return "%s%s" % (
            LEGAL_SERVICE_CODE_PREFIX.get(service_type, ""),
            self._get_service_client_sequence(client_code),
        )

    @api.model
    def _get_service_client_sequence(self, client_code):
        code = (client_code or "").strip()
        for separator in ("/", "-"):
            if separator in code:
                parts = [part for part in code.split(separator) if part]
                if parts:
                    return parts[-1]
        return code

    def _compute_service_counts(self):
        project_ids = self.ids
        count_maps = {
            "litigation_case_count": self._read_project_count("qlk.case", project_ids),
            "corporate_case_count": self._read_project_count("qlk.corporate.case", project_ids),
            "arbitration_case_count": self._read_project_count("qlk.arbitration.case", project_ids),
            "pre_litigation_count": self._read_project_count("qlk.pre.litigation", project_ids),
        }
        for project in self:
            for field_name, count_map in count_maps.items():
                project[field_name] = count_map.get(project.id, 0)

    @api.depends(
        "client_id",
        "client_id.vat",
        "client_id.company_registry",
        "client_id.ref",
        "client_id.street",
        "client_id.street2",
        "client_id.city",
        "client_id.state_id",
        "client_id.zip",
        "client_id.country_id",
    )
    def _compute_client_profile_fields(self):
        for project in self:
            client = project.client_id
            if not client:
                project.client_qid_cr = False
                project.client_address = False
                continue
            project.client_qid_cr = client.vat or client.company_registry or client.ref
            project.client_address = client._display_address() or False

    def _read_project_count(self, model_name, project_ids):
        if not project_ids or model_name not in self.env:
            return {}
        model = self.env[model_name]
        if "project_id" not in model._fields:
            return {}
        table = model._table
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = %s
               AND column_name = 'project_id'
             LIMIT 1
            """,
            [table],
        )
        if not self.env.cr.fetchone():
            return {}
        groups = model.read_group(
            [("project_id", "in", project_ids)],
            ["project_id"],
            ["project_id"],
        )
        return {
            group["project_id"][0]: group.get("__count", 0)
            for group in groups
            if group.get("project_id")
        }

    @api.depends("lawyer_id")
    def _compute_lawyer_costs(self):
        for project in self:
            project.lawyer_hour_cost = project.lawyer_id.lawyer_hour_cost or 0.0

    @api.depends("lawyer_hour_cost", "lawyer_hours", "additional_project_cost")
    def _compute_totals(self):
        for project in self:
            total = (project.lawyer_hour_cost or 0.0) * (project.lawyer_hours or 0.0)
            project.lawyer_total_cost = total
            project.total_cost_all = total + (project.additional_project_cost or 0.0)


    @api.depends("mp_id")
    def _compute_user_permissions(self):
        current_user = self.env.user
        for project in self:
            project.is_mp_user = bool(project.mp_id and project.mp_id == current_user)

    @api.model_create_multi
    def create(self, vals_list):
        sequence_cache = {}
        for vals in vals_list:
            engagement = vals.get("engagement_letter_id") and self.env["bd.engagement.letter"].browse(vals["engagement_letter_id"])
            if vals.get("engagement_letter_id") or vals.get("service_type"):
                self._ensure_legal_manager()
            if engagement and self.with_context(active_test=False).search_count([("engagement_letter_id", "=", engagement.id)]):
                raise UserError(_("A project has already been created for this engagement letter."))
            if engagement:
                vals.setdefault("client_id", engagement.partner_id.id)
                vals.setdefault("contract_type", engagement.contract_type)
                vals.setdefault("service_type", self._get_service_type_from_engagement(engagement))
                vals.setdefault("lawyer_id", engagement.lawyer_employee_id.id)
                vals.setdefault("legal_fee_amount", engagement.legal_fee_amount or engagement.total_amount)
                vals.setdefault("engagement_reference", engagement.code)
                vals.setdefault("billing_type", engagement.billing_type)
                vals.setdefault("retainer_type", engagement.retainer_type)
            client_id = vals.get("client_id")
            client = client_id and self.env["res.partner"].browse(client_id) or False
            if client:
                vals.setdefault("client_code", client._get_client_code())
            if client and (not vals.get("code") or vals.get("code") == "/"):
                client_code = vals.get("client_code") or client._get_client_code()
                vals["code"] = self._generate_project_code(client.id, client_code, sequence_cache)
            if client and vals.get("service_type") and not vals.get("service_code"):
                client_code = vals.get("client_code") or client._get_client_code()
                vals["service_code"] = self._build_service_code(client_code, vals["service_type"])
        projects = super().create(vals_list)
        projects._handle_translation_notifications()
        projects._copy_partner_attachments()
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        # projects._check_hours_logged()
        return projects

    def _generate_project_code(self, partner_id, client_code, sequence_cache):
        prefix = f"{client_code or '00/000'}/PRJ"
        cache_value = sequence_cache.get(partner_id)
        if cache_value is None:
            last_project = (
                self.with_context(active_test=False)
                .search([("client_id", "=", partner_id), ("code", "like", f"{prefix}%")], order="code desc", limit=1)
            )
            last_number = 0
            if last_project and last_project.code:
                try:
                    last_number = int(last_project.code.split("PRJ")[-1])
                except (ValueError, IndexError):
                    last_number = 0
        else:
            last_number = cache_value
        next_number = (last_number or 0) + 1
        sequence_cache[partner_id] = next_number
        return f"{prefix}{next_number:03d}"

    def _sync_client_code_from_partner(self):
        for project in self:
            client = project.client_id
            if not client:
                continue
            client_code = client._get_client_code()
            updates = {"client_code": client_code}
            code = project.code or ""
            if code and "/PRJ" in code:
                suffix = code.split("/PRJ", 1)[1]
                if suffix:
                    updates["code"] = f"{client_code}/PRJ{suffix}"
            else:
                updates["code"] = project._generate_project_code(client.id, client_code, {})
            project.with_context(skip_project_code_sync=True).write(updates)


    def write(self, vals):
        vals = dict(vals)
        if "contract_type" in vals and not self.env.context.get("allow_project_contract_type_update"):
            raise UserError(_("Contract Type is locked after project creation."))
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        # if self._has_new_task_command(vals.get("qlk_task_ids")):
        #     return super().write(vals)
        # if self._requires_new_task_on_write(vals):
        #     self._raise_missing_hours_error()
        if "lawyer_id" in vals:
            new_value = vals.get("lawyer_id")
            for project in self:
                project._check_lawyer_assignment_rights(new_value)
        previous_states = {project.id: project.mini_state for project in self}
        res = super().write(vals)
        if not self.env.context.get("skip_translation_notification"):
            self._handle_translation_notifications()
        done_records = self.filtered(
            lambda p: p.is_mini_project
            and p.mini_state == "done"
            and previous_states.get(p.id) != "done"
        )
        if done_records:
            done_records._notify_bd_completion()
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        # self._check_hours_logged()
        return res

    def _get_service_type_from_engagement(self, engagement):
        service_type = engagement.service_type or engagement.retainer_type or engagement.engagement_type or "corporate"
        if service_type == "mixed":
            return False
        if service_type in LEGAL_SERVICE_CODE_PREFIX:
            return service_type
        if "arbitration" in service_type:
            return "arbitration"
        if "litigation" in service_type:
            return "litigation"
        return "corporate"

    def _ensure_legal_manager(self):
        if self.env.is_superuser():
            return True
        if any(self.env.user.has_group(group) for group in LEGAL_MANAGER_GROUPS):
            return True
        raise UserError(_("Only Managers or Assistant Managers can perform this action."))

    @api.constrains("client_id", "engagement_letter_id", "service_type")
    def _check_legal_project_client(self):
        for project in self:
            if (project.engagement_letter_id or project.service_type) and not project.client_id:
                raise ValidationError(_("A legal project cannot be created without a client."))
            if project.engagement_letter_id:
                duplicate = self.with_context(active_test=False).search_count([
                    ("engagement_letter_id", "=", project.engagement_letter_id.id),
                    ("id", "!=", project.id),
                ])
                if duplicate:
                    raise ValidationError(_("A project has already been created for this engagement letter."))

    def _ensure_project_ready_for_service(self, service_type):
        self.ensure_one()
        self._ensure_legal_manager()
        if not self.client_id:
            raise UserError(_("Set a client before creating service records."))
        if not self.service_type:
            raise UserError(_("Set a service type before creating service records."))
        if self.service_type != service_type:
            raise UserError(_("This project service type does not allow this service record."))
        if not self.service_code:
            client_code = self.client_code or self.client_id._get_client_code()
            service_code = self._build_service_code(client_code, self.service_type)
            if service_code:
                self.write({"service_code": service_code})
        return True

    def _service_duplicate(self, model_name):
        return self.env[model_name].search([("project_id", "=", self.id)], limit=1)

    def _service_action(self, model_name, record, title):
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_name,
            "res_id": record.id,
            "view_mode": "form",
            "target": "current",
        }

    def _service_default_context(self):
        self.ensure_one()
        return {
            "default_project_id": self.id,
            "default_client_id": self.client_id.id,
            "default_service_code": self.service_code,
            "default_engagement_id": self.engagement_letter_id.id,
        }

    def action_create_litigation_case(self):
        self._ensure_project_ready_for_service("litigation")
        existing = self._service_duplicate("qlk.case")
        if existing:
            raise UserError(_("A litigation case already exists for this project."))
        degree = self.engagement_letter_id.litigation_degree_ids[:1] if self.engagement_letter_id else False
        context = self._service_default_context()
        context.update(
            {
                "default_name": self.service_code or self.name,
                "default_name2": self.name,
                "default_client_ids": self.client_id.ids,
                "default_employee_id": self.lawyer_id.id,
                "default_litigation_flow": "litigation",
                "default_litigation_degree_id": degree.id if degree else False,
                "default_litigation_level_id": degree.level_id.id if degree and degree.level_id else False,
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

    def action_create_corporate_case(self):
        self._ensure_project_ready_for_service("corporate")
        existing = self._service_duplicate("qlk.corporate.case")
        if existing:
            raise UserError(_("A corporate record already exists for this project."))
        if not self.lawyer_id:
            raise UserError(_("Assign a lawyer before creating a corporate record."))
        record = self.env["qlk.corporate.case"].create(
            {
                "name": self.service_code or self.name,
                "project_id": self.id,
                "engagement_id": self.engagement_letter_id.id,
                "client_id": self.client_id.id,
                "service_code": self.service_code,
                "responsible_employee_id": self.lawyer_id.id,
            }
        )
        return self._service_action("qlk.corporate.case", record, _("Corporate"))

    def action_create_arbitration_case(self):
        self._ensure_project_ready_for_service("arbitration")
        existing = self._service_duplicate("qlk.arbitration.case")
        if existing:
            raise UserError(_("An arbitration record already exists for this project."))
        record = self.env["qlk.arbitration.case"].create(
            {
                "name": self.service_code or self.name,
                "project_id": self.id,
                "engagement_id": self.engagement_letter_id.id,
                "claimant_id": self.client_id.id,
                "service_code": self.service_code,
                "responsible_employee_id": self.lawyer_id.id,
            }
        )
        return self._service_action("qlk.arbitration.case", record, _("Arbitration"))

    def action_create_pre_litigation(self):
        self._ensure_project_ready_for_service("pre_litigation")
        existing = self._service_duplicate("qlk.pre.litigation")
        if existing:
            raise UserError(_("A pre-litigation record already exists for this project."))
        record = self.env["qlk.pre.litigation"].create(
            {
                "name": self.service_code or _("New Pre-Litigation"),
                "project_id": self.id,
                "engagement_id": self.engagement_letter_id.id,
                "client_id": self.client_id.id,
                "service_code": self.service_code,
                "lawyer_employee_id": self.lawyer_id.id,
                "subject": self.name,
            }
        )
        return self._service_action("qlk.pre.litigation", record, _("Pre-Litigation"))

    def action_open_litigation_cases(self):
        self.ensure_one()
        return self._action_open_project_records("qlk.case", _("Cases"))

    def action_open_corporate_cases(self):
        self.ensure_one()
        return self._action_open_project_records("qlk.corporate.case", _("Corporate"))

    def action_open_arbitration_cases(self):
        self.ensure_one()
        return self._action_open_project_records("qlk.arbitration.case", _("Arbitration"))

    def action_open_pre_litigation(self):
        self.ensure_one()
        return self._action_open_project_records("qlk.pre.litigation", _("Pre-Litigation"))

    def _action_open_project_records(self, model_name, title):
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_name,
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.id)],
            "context": dict(self._service_default_context()),
        }

    def _raise_missing_hours_error(self):
        model_label = self._description or self._name
        raise UserError(
            _(
                "⚠️ يجب إدخال الساعات قبل حفظ السجل في %(model)s.\n"
                "⚠️ Hours must be logged before saving this %(model)s."
            )
            % {"model": model_label}
        )

    def _check_hours_logged(self):
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        return
        Task = self.env["qlk.task"]
        for project in self:
            if not Task.search_count([("project_id", "=", project.id)]):
                project._raise_missing_hours_error()

    def _requires_new_task_on_write(self, vals):
        # NOTE: Hours enforcement temporarily disabled; keep for future re-enable.
        return False
        fields_changed = set(vals) - {"qlk_task_ids"}
        if not fields_changed:
            return False
        return not self._has_new_task_command(vals.get("qlk_task_ids"))

    @staticmethod
    def _has_new_task_command(commands):
        for command in commands or []:
            if isinstance(command, (list, tuple)) and command and command[0] == 0:
                return True
        return False

    def _check_lawyer_assignment_rights(self, new_lawyer_id):
        self.ensure_one()
        if not self.is_mini_project:
            return True
        current_id = self.lawyer_id.id if self.lawyer_id else False
        if current_id == new_lawyer_id:
            return True
        if self.env.is_superuser():
            return True
        if not self.mp_id:
            raise UserError(_("Set a Mini Project Manager before assigning a lawyer."))
        if self.mp_id != self.env.user:
            raise UserError(_("Only %s can assign or change the lawyer.") % self.mp_id.display_name)
        return True

    def action_assign_lawyer(self):
        for project in self:
            project._ensure_mp_user()
            if not project.lawyer_id:
                raise UserError(_("Select a lawyer before confirming the assignment."))
            updates = {"lawyer_assigned": True}
            if project.mini_state == "draft":
                updates["mini_state"] = "in_progress"
            project.with_context(skip_translation_notification=True).write(updates)
            partner_ids = []
            if project.bd_user_id and project.bd_user_id.partner_id:
                partner_ids.append(project.bd_user_id.partner_id.id)
            body = _(
                "Lawyer %(lawyer)s has been assigned by %(user)s."
            ) % {
                "lawyer": project.lawyer_id.display_name,
                "user": project.env.user.display_name,
            }
            kwargs = {"body": body}
            if partner_ids:
                kwargs["partner_ids"] = partner_ids
            project.message_post(**kwargs)
        return True

    def action_complete_mini_project(self):
        for project in self:
            project._ensure_mp_user()
            if not project.lawyer_assigned or not project.lawyer_id:
                raise UserError(_("Assign a lawyer before completing the mini project."))
            project.write({"mini_state": "done"})
        return True

    def _ensure_mp_user(self):
        self.ensure_one()
        if not self.is_mini_project:
            return
        if not self.mp_id:
            raise UserError(_("Please assign a Mini Project Manager before performing this action."))
        if self.env.is_superuser():
            return
        if self.env.user != self.mp_id:
            raise UserError(_("Only the assigned Mini Project Manager can perform this action."))

    def _notify_bd_completion(self):
        for project in self:
            if not project.bd_user_id or not project.bd_user_id.partner_id:
                continue
            message = _(
                "Mini Project completed. Lawyer %(lawyer)s is assigned to %(project)s."
            ) % {
                "lawyer": project.lawyer_id.display_name if project.lawyer_id else _("(not set)"),
                "project": project.display_name,
            }
            project.message_post(
                body=message,
                partner_ids=[project.bd_user_id.partner_id.id],
            )

    def _handle_translation_notifications(self):
        for project in self:
            if project.needs_translation and not project.translation_requested:
                project._notify_translation_required()

    def _notify_translation_required(self):
        self.ensure_one()
        partner_ids = []
        if self.mp_id and self.mp_id.partner_id:
            partner_ids.append(self.mp_id.partner_id.id)
        body = _(
            "Translation is required for the documents of %(project)s. Please coordinate the request."
        ) % {"project": self.display_name}
        kwargs = {"body": body}
        if partner_ids:
            kwargs["partner_ids"] = partner_ids
        self.message_post(**kwargs)
        if self.mp_id:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=self.mp_id.id,
                summary=_("Translation Request"),
                note=_("Please request document translation for %s.") % self.display_name,
            )
        self.with_context(skip_translation_notification=True).write({"translation_requested": True})

    def action_view_client_attachments(self):
        self.ensure_one()
        partner = self.client_id
        if not partner:
            raise UserError(_("Please select a client before opening attachments."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Client Documents"),
            "res_model": "qlk.client.document",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", partner.id)],
            "context": {
                "default_partner_id": partner.id,
                "default_related_model": self._name,
                "default_related_res_id": self.id,
            },
        }


    def _copy_partner_attachments(self):
        Attachment = self.env["ir.attachment"].sudo()
        partners = self.mapped("client_id")
        if not partners:
            return
        partner_attachments = Attachment.search(
            [("res_model", "=", "res.partner"), ("res_id", "in", partners.ids)]
        )
        attachments_by_partner = {}
        for attachment in partner_attachments:
            attachments_by_partner.setdefault(attachment.res_id, []).append(attachment)
        for project in self:
            partner = project.client_id
            if not partner:
                continue
            for attachment in attachments_by_partner.get(partner.id, []):
                attachment.copy(
                    {
                        "res_model": project._name,
                        "res_id": project.id,
                    }
                )
