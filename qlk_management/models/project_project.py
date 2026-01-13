# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

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
    ("litigation_arbitration", "Litigation + Arbitration"),
    ("corporate_arbitration", "Corporate + Arbitration"),
    ("litigation_corporate_arbitration", "Litigation + Corporate + Arbitration"),
]


class ProjectProject(models.Model):
    _inherit = "project.project"

    cost_calculation_id = fields.Many2one("cost.calculation", string="Cost Calculation")
    client_document_ids = fields.One2many(
        related="partner_id.client_document_ids",
        string="Client Documents",
    )
    lawyer_id = fields.Many2one("hr.employee", string="Lawyer")
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
    project_type = fields.Selection(
        selection=PROJECT_TYPE_SELECTION,
        string="Project Type",
        default="corporate",
    )
    retainer_type = fields.Selection(
        selection=RETAINER_TYPE_SELECTION,
        string="Retainer Type",
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
            partner_id = vals.get("partner_id")
            partner = partner_id and self.env["res.partner"].browse(partner_id) or False
            if partner:
                vals.setdefault("client_code", partner._get_client_code())
            if partner and (not vals.get("code") or vals.get("code") == "/"):
                client_code = vals.get("client_code") or partner._get_client_code()
                vals["code"] = self._generate_project_code(partner.id, client_code, sequence_cache)
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
                .search([("partner_id", "=", partner_id), ("code", "like", f"{prefix}%")], order="code desc", limit=1)
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

    def write(self, vals):
        vals = dict(vals)
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
        partner = self.partner_id
        if not partner:
            raise UserError(_("Please select a client before opening attachments."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Client Documents"),
            "res_model": "qlk.client.document",
            "view_mode": "tree,form",
            "domain": [("partner_id", "=", partner.id)],
            "context": {
                "default_partner_id": partner.id,
                "default_related_model": self._name,
                "default_related_res_id": self.id,
            },
        }


    def _copy_partner_attachments(self):
        Attachment = self.env["ir.attachment"].sudo()
        partners = self.mapped("partner_id")
        if not partners:
            return
        partner_attachments = Attachment.search(
            [("res_model", "=", "res.partner"), ("res_id", "in", partners.ids)]
        )
        attachments_by_partner = {}
        for attachment in partner_attachments:
            attachments_by_partner.setdefault(attachment.res_id, []).append(attachment)
        for project in self:
            partner = project.partner_id
            if not partner:
                continue
            for attachment in attachments_by_partner.get(partner.id, []):
                attachment.copy(
                    {
                        "res_model": project._name,
                        "res_id": project.id,
                    }
                )
