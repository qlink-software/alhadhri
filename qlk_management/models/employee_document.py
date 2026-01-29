# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class QLKEmployeeDocument(models.Model):
    _name = "qlk.employee.document"
    _description = "Employee Contract and NDA Document"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    doc_type = fields.Selection(
        [
            ("contract", "Contract"),
            ("nda", "NDA"),
            ("other", "Other"),
        ],
        default="contract",
        tracking=True,
        required=True,
    )
    name = fields.Char(string="Document Title")
    template_ref = fields.Char(string="Template Reference")
    date_start = fields.Date()
    date_end = fields.Date()
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("waiting_approval", "Waiting Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("signed", "Signed"),
        ],
        default="draft",
        tracking=True,
    )
    requested_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        tracking=True,
        required=True,
    )
    approved_by = fields.Many2one("res.users", readonly=True, tracking=True)
    approved_date = fields.Datetime(readonly=True, tracking=True)
    rejection_reason = fields.Text()

    job_id = fields.Many2one(
        "hr.job",
        related="employee_id.job_id",
        readonly=True,
        store=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        related="employee_id.department_id",
        readonly=True,
        store=True,
    )
    work_email = fields.Char(related="employee_id.work_email", readonly=True)
    work_phone = fields.Char(related="employee_id.work_phone", readonly=True)

    signed_attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_employee_document_attachment_rel",
        "document_id",
        "attachment_id",
        string="Signed Documents",
        domain="[('res_model','=','qlk.employee.document'),('res_id','=',id)]",
    )

    def _get_doc_type_label(self, doc_type):
        selection = dict(self._fields["doc_type"].selection)
        return selection.get(doc_type, "")

    @api.onchange("employee_id", "doc_type")
    def _onchange_employee_doc_type(self):
        for record in self:
            if record.name:
                continue
            if not record.employee_id:
                continue
            label = record._get_doc_type_label(record.doc_type)
            if label:
                record.name = "%s - %s" % (label, record.employee_id.name)

    @api.model
    def create(self, vals):
        if not vals.get("name"):
            employee_name = ""
            employee_id = vals.get("employee_id")
            if employee_id:
                employee = self.env["hr.employee"].browse(employee_id)
                employee_name = employee.name or ""
            doc_type = vals.get("doc_type") or "contract"
            label = self._get_doc_type_label(doc_type)
            if label and employee_name:
                vals["name"] = "%s - %s" % (label, employee_name)
            elif label:
                vals["name"] = label
        return super().create(vals)

    def _check_manager_group(self):
        if not self.env.user.has_group("qlk_management.group_hr_nda_manager"):
            raise AccessError(_("You are not allowed to approve or reject documents."))

    def action_submit_for_approval(self):
        for record in self:
            if record.status != "draft":
                raise UserError(_("Only draft documents can be submitted for approval."))
            if record.requested_by != self.env.user:
                raise AccessError(_("Only the requester can submit this document."))
            record.write({"status": "waiting_approval"})
        return True

    def action_approve(self):
        self._check_manager_group()
        for record in self:
            if record.status != "waiting_approval":
                raise UserError(_("Only documents waiting for approval can be approved."))
            record.sudo().with_context(allow_status_update=True).write(
                {
                    "status": "approved",
                    "approved_by": self.env.user.id,
                    "approved_date": fields.Datetime.now(),
                    "rejection_reason": False,
                }
            )
        return True

    def action_reject(self):
        self._check_manager_group()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Document"),
            "res_model": "qlk.employee.document.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_document_id": self.id,
            },
        }

    def action_mark_signed(self):
        self._check_manager_group()
        for record in self:
            if record.status != "approved":
                raise UserError(_("Only approved documents can be marked as signed."))
            record.sudo().with_context(allow_status_update=True).write({"status": "signed"})
        return True

    def write(self, vals):
        if not self.env.context.get("allow_status_update"):
            protected_states = ("approved", "signed")
            allowed_fields = {"signed_attachment_ids"}
            for record in self:
                if record.status in protected_states:
                    if any(field not in allowed_fields for field in vals):
                        raise UserError(
                            _("Approved or signed documents are read-only except attachments.")
                        )
                if not self.env.user.has_group("qlk_management.group_hr_nda_manager"):
                    if record.requested_by != self.env.user:
                        raise AccessError(_("You can only modify your own documents."))
                    if record.status != "draft":
                        raise UserError(_("Only draft documents can be edited."))
        return super().write(vals)
