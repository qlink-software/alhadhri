# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PreLitigation(models.Model):
    _name = "qlk.pre.litigation"
    _description = "Pre-Litigation Case"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("translation", "Translation"),
        ("memo", "Drafting Memo"),
        ("review", "Review & Approval"),
        ("client_approval", "Client Approval"),
        ("office_sign", "Signature & Stamp"),
        ("registration", "Registration"),
        ("correction", "Claim Correction"),
        ("fee_payment", "Fee Payment"),
        ("done", "Done"),
    ]

    name = fields.Char(string="Reference", required=True, copy=False, tracking=True, default="New")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    project_id = fields.Many2one("qlk.project", string="Related Project", tracking=True)
    case_id = fields.Many2one("qlk.case", string="Litigation Case", tracking=True)
    client_id = fields.Many2one("res.partner", string="Client", required=True, tracking=True, domain="[('customer', '=', True)]")
    opponent_id = fields.Many2one("res.partner", string="Opponent", domain="[('is_opponent', '=', True)]", tracking=True)
    subject = fields.Char(string="Subject", tracking=True)
    description = fields.Text(string="Summary / Notes")
    state = fields.Selection(selection=STATE_SELECTION, default="draft", tracking=True, required=True)
    lawyer_employee_id = fields.Many2one("hr.employee", string="Responsible Lawyer", tracking=True)
    lawyer_user_id = fields.Many2one("res.users", related="lawyer_employee_id.user_id", store=True, readonly=True)
    office_manager_id = fields.Many2one("res.users", string="Office Manager", tracking=True)
    translation_line_ids = fields.One2many("qlk.pre.litigation.translation", "pre_litigation_id", string="Translation Subtasks")
    translated_document_ids = fields.Many2many(
        "ir.attachment",
        "qlk_pre_lit_translated_rel",
        "pre_litigation_id",
        "attachment_id",
        string="Translated Documents",
        tracking=True,
    )
    client_document_ids = fields.Many2many(
        "ir.attachment",
        "qlk_pre_lit_client_doc_rel",
        "pre_litigation_id",
        "attachment_id",
        string="Client Documents",
    )
    translation_notes = fields.Text(string="Translation Notes")
    memo_notes = fields.Text(string="Memo Draft Notes")
    review_notes = fields.Text(string="Review Notes")
    client_approval_notes = fields.Text(string="Client Approval Notes")
    office_sign_notes = fields.Text(string="Office Signature Notes")
    registration_details = fields.Text(string="Registration Details")
    correction_notes = fields.Text(string="Correction Notes")
    approval_note = fields.Text(string="Approvals")
    fee_payment_note = fields.Text(string="Fee Payment Notes")
    fee_payment_amount = fields.Monetary(string="Fee Amount")
    fee_payment_reference = fields.Char(string="Fee Payment Reference")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    lawyer_note = fields.Html(string="Lawyer Notes")
    translated_count = fields.Integer(string="Translated Files", compute="_compute_translated_count")

    @api.depends("translated_document_ids")
    def _compute_translated_count(self):
        for record in self:
            record.translated_count = len(record.translated_document_ids)

    @api.model
    def create(self, vals):
        if not vals.get("name") or vals.get("name") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("qlk.pre.litigation") or _("New Pre-Litigation")
        if not vals.get("company_id"):
            vals["company_id"] = self.env.company.id
        record = super().create(vals)
        record._ensure_translation_subtask()
        record._link_back_references()
        return record

    def write(self, vals):
        result = super().write(vals)
        if any(field in vals for field in ("project_id", "case_id")):
            self._link_back_references()
        return result

    def _link_back_references(self):
        for record in self:
            if record.case_id and "pre_litigation_id" in record.case_id._fields:
                record.case_id.pre_litigation_id = record.id
            if record.project_id and "pre_litigation_id" in record.project_id._fields and not record.project_id.pre_litigation_id:
                record.project_id.pre_litigation_id = record.id

    def _ensure_translation_subtask(self):
        for record in self:
            if not record.translation_line_ids:
                self.env["qlk.pre.litigation.translation"].create(
                    {
                        "pre_litigation_id": record.id,
                        "name": _("Translation of Documents"),
                        "responsible_id": record.office_manager_id.id or record.lawyer_user_id.id,
                    }
                )

    def _notify_office_manager_translation(self, translation, attachment_ids):
        self.ensure_one()
        partner = self.office_manager_id.partner_id if self.office_manager_id else False
        if not partner:
            return
        attachment_names = ", ".join(
            self.env["ir.attachment"].browse(attachment_ids).mapped("name")
        )
        body = _(
            "New translation request documents have been uploaded for %(ref)s: %(docs)s",
            ref=self.display_name,
            docs=attachment_names or "-",
        )
        self.message_post(body=body, partner_ids=partner.ids)

    def _notify_lawyer_translation(self, translation, attachment_ids):
        self.ensure_one()
        partner = self.lawyer_user_id.partner_id if self.lawyer_user_id else False
        if not partner:
            return
        attachment_names = ", ".join(
            self.env["ir.attachment"].browse(attachment_ids).mapped("name")
        )
        body = _(
            "Translated documents are ready for %(ref)s: %(docs)s",
            ref=self.display_name,
            docs=attachment_names or "-",
        )
        self.message_post(body=body, partner_ids=partner.ids)

    def _link_translated_documents(self, attachment_ids):
        for record in self:
            if attachment_ids:
                record.translated_document_ids = [(4, att_id) for att_id in attachment_ids]

    def action_view_case(self):
        self.ensure_one()
        action = self.env.ref("qlk_law.act_open_qlk_case_view", raise_if_not_found=False)
        if action and self.case_id:
            return action.with_context(active_id=self.case_id.id, active_ids=[self.case_id.id])
        return False

    def action_create_litigation_case(self):
        self.ensure_one()
        if self.case_id:
            return self.action_view_case()
        if self.state != "fee_payment":
            raise UserError(_("The pre-litigation must reach the Fee Payment stage before creating a case."))
        case_vals = self._prepare_case_vals()
        case = self.env["qlk.case"].create(case_vals)
        attachments = (self.client_document_ids | self.translated_document_ids).ids
        if attachments:
            case.attachment_ids = [(4, att) for att in attachments]
        self.case_id = case.id
        if "pre_litigation_id" in case._fields:
            case.pre_litigation_id = self.id
        if self.project_id and not self.project_id.case_id:
            self.project_id.case_id = case.id
        self.state = "done"
        self.message_post(
            body=_("Litigation case %(case)s has been created from this pre-litigation.", case=case.display_name)
        )
        return self.action_view_case()

    def _prepare_case_vals(self):
        self.ensure_one()
        name = self.subject or self.client_id.display_name
        vals = {
            "name": name,
            "client_id": self.client_id.id,
            "opponent_id": self.opponent_id.id if self.opponent_id else False,
            "subject": self.subject or name,
            "description": self.description,
            "company_id": self.company_id.id,
            "litigation_flow": "litigation",
        }
        if self.project_id:
            vals.update(
                {
                    "name2": self.project_id.code or self.project_id.name,
                    "client_capacity": self.project_id.client_capacity,
                }
            )
        if self.lawyer_employee_id:
            vals["employee_id"] = self.lawyer_employee_id.id
        return vals


class PreLitigationTranslation(models.Model):
    _name = "qlk.pre.litigation.translation"
    _description = "Pre-Litigation Translation Subtask"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Title", required=True, default=lambda self: _("Translation of Documents"))
    pre_litigation_id = fields.Many2one(
        "qlk.pre.litigation",
        string="Pre-Litigation",
        required=True,
        ondelete="cascade",
    )
    responsible_id = fields.Many2one("res.users", string="Responsible")
    deadline = fields.Date(string="Deadline")
    request_attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_pre_lit_translation_request_rel",
        "translation_id",
        "attachment_id",
        string="Source Documents",
    )
    translated_attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_pre_lit_translation_result_rel",
        "translation_id",
        "attachment_id",
        string="Translated Documents",
    )
    note = fields.Text(string="Notes")
    state = fields.Selection(
        selection=[("pending", "Pending"), ("translated", "Translated")],
        default="pending",
        tracking=True,
    )

    def write(self, vals):
        monitored = "translated_attachment_ids" in vals or "request_attachment_ids" in vals
        if not monitored:
            return super().write(vals)

        before_data = {
            record.id: (
                set(record.request_attachment_ids.ids),
                set(record.translated_attachment_ids.ids),
            )
            for record in self
        }
        if "translated_attachment_ids" in vals and not vals.get("state"):
            vals.setdefault("state", "translated")
        res = super().write(vals)
        for record in self:
            previous_request, previous_translated = before_data.get(record.id, (set(), set()))
            new_request = set(record.request_attachment_ids.ids) - previous_request
            new_translated = set(record.translated_attachment_ids.ids) - previous_translated
            if new_request:
                record.pre_litigation_id._notify_office_manager_translation(record, list(new_request))
            if new_translated:
                record.pre_litigation_id._notify_lawyer_translation(record, list(new_translated))
                record.pre_litigation_id._link_translated_documents(list(new_translated))
        return res
