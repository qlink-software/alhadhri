# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديول إدارة بيانات العملاء (Clients)
# يوفر هذا الملف جميع الحقول المساعدة للمرفقات وتحذيرات المستندات وتنبيهات
# انتهاء صلاحية التوكيلات بالإضافة إلى كود العميل بعد توقيع اتفاقية EL.
# ------------------------------------------------------------------------------
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    indust_date = fields.Date(string="Date")
    attachment_id = fields.Many2one("ir.attachment", string="Attachment", ondelete="set null", index=True)

    task_ids = fields.One2many("task", "crm_id", string="Working Hours")
    qlk_task_ids = fields.One2many("qlk.task", "partner_id", string="Tasks / Hours")
    client_document_ids = fields.One2many(
        "qlk.client.document",
        "partner_id",
        string="Client Documents",
    )
    client_attachment_ids = fields.Many2many(
        "ir.attachment",
        "res_partner_client_attachment_rel",
        "partner_id",
        "attachment_id",
        string="Attachments",
    )
    hours_logged_ok = fields.Boolean(
        string="Hours Logged?",
        compute="_compute_hours_logged_ok",
        store=True,
        default=False,
        help="Automatically toggled based on logging tasks/hours",
    )
    bd_client_code = fields.Char(string="Client Code", copy=False, readonly=True)
    code = fields.Char(string="Client Code", default="/", copy=False, readonly=True)
    client_year = fields.Integer(string="Client Year", default=lambda self: self._default_client_year())

    # ------------------------------------------------------------------------------
    # دالة تحدد المستندات المطلوبة حسب نوع العميل (شركة أو فرد).
    # ------------------------------------------------------------------------------
    def _get_required_document_types(self):
        if self.company_type == "company":
            return ["company_commercial_register", "company_trade_license", "company_poa"]
        return ["individual_id", "individual_poa"]

    # def get_missing_document_labels(self):
    #     """Return a list of missing required document labels for the partner."""
    #     self.ensure_one()
    #     doc_model = self.env["qlk.client.document"]
    #     doc_labels = dict(doc_model._fields["doc_type"].selection)
    #     required = self._get_required_document_types()
    #     available = {doc.doc_type for doc in self.client_document_ids if doc.is_uploaded}
    #     return [doc_labels.get(doc_type, doc_type) for doc_type in required if doc_type not in available]

    # ------------------------------------------------------------------------------
    # دالة تحسب أقرب تاريخ لانتهاء POA وتصيغ رسالة تذكير للواجهة.
    # ------------------------------------------------------------------------------
    # @api.depends("client_document_ids.poa_expiration_date")
    # def _compute_poa_expiration_info(self):
    #     today = fields.Date.context_today(self)
    #     for partner in self:
    #         upcoming_doc = False
    #         reminder = False
    #         dated_docs = [
    #             doc for doc in partner.client_document_ids if doc.poa_expiration_date and doc.is_uploaded
    #         ]
    #         if dated_docs:
    #             upcoming_doc = min(dated_docs, key=lambda doc: doc.poa_expiration_date)
    #         if upcoming_doc:
    #             partner.poa_next_expiration_date = upcoming_doc.poa_expiration_date
    #             delta = (upcoming_doc.poa_expiration_date - today).days
    #             if delta < 0:
    #                 reminder = _("POA is already expired since %s") % upcoming_doc.poa_expiration_date
    #             else:
    #                 reminder = _("POA expires in %s days (%s)") % (delta, upcoming_doc.poa_expiration_date)
    #         else:
    #             partner.poa_next_expiration_date = False
    #         partner.poa_expiry_reminder = reminder

    @api.constrains("phone", "mobile", "email")
    def _check_contact_channels(self):
        for partner in self:
            if partner.customer_rank <= 0:
                continue
            missing = []
            if not partner.mobile:
                missing.append(_("Mobile"))
            if not partner.email:
                missing.append(_("Email"))
            if missing:
                raise ValidationError(
                    _("The following fields are required for clients: %s") % ", ".join(missing)
                )

    @api.constrains("email", "mobile")
    def _check_unique_contact_fields(self):
        partner_model = self.env["res.partner"].sudo()
        for partner in self:
            duplicates = []
            if partner.email:
                duplicate_email = partner_model.search(
                    [("email", "=", partner.email), ("id", "!=", partner.id)], limit=1
                )
                if duplicate_email:
                    duplicates.append(_("Email"))
            if partner.mobile:
                duplicate_mobile = partner_model.search(
                    [("mobile", "=", partner.mobile), ("id", "!=", partner.id)], limit=1
                )
                if duplicate_mobile:
                    duplicates.append(_("Mobile"))
            if duplicates:
                raise UserError(
                    _("The following contact fields must be unique across partners: %s.")
                    % ", ".join(duplicates)
                )

    @api.model
    def _default_client_year(self):
        today = fields.Date.context_today(self)
        return today.year

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            client_year = vals.get("client_year") or self._default_client_year()
            client_year = int(client_year)
            vals["client_year"] = client_year
            if not vals.get("code") or vals.get("code") == "/":
                vals["code"] = self._generate_partner_code(client_year)
        records = super().create(vals_list)
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
        # records._check_hours_logged()
        return records

    def write(self, vals):
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
        # if self._has_new_task_command(vals.get("qlk_task_ids")):
        #     return super().write(vals)
        # if self._requires_new_task_on_write(vals):
        #     self._raise_missing_hours_error()
        res = super().write(vals)
        if "client_year" in vals and not self.env.context.get("skip_year_sync"):
            for partner in self:
                partner._update_code_for_year_change()
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
        # self._check_hours_logged()
        return res

    @api.depends("qlk_task_ids")
    def _compute_hours_logged_ok(self):
        for partner in self:
            partner.hours_logged_ok = bool(partner.qlk_task_ids)

    @api.onchange("qlk_task_ids")
    def _onchange_qlk_task_ids(self):
        for partner in self:
            partner.hours_logged_ok = bool(partner.qlk_task_ids)

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
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
        # Task = self.env["qlk.task"]
        # for partner in self:
        #     if not Task.search_count([("partner_id", "=", partner.id)]):
        #         partner._raise_missing_hours_error()
        return True

    def _requires_new_task_on_write(self, vals):
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

    def action_create_bd_proposal(self):
        self.ensure_one()
        partner = self.commercial_partner_id or self
        form_view = self.env.ref("qlk_management.view_bd_proposal_form")
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Proposal"),
            "res_model": "bd.proposal",
            "view_mode": "form",
            "views": [(form_view.id, "form")],
            "target": "current",
            "context": {
                "default_partner_id": partner.id,
                "default_client_id": partner.id,
            },
        }

    def ensure_client_code(self):
        """Ensure partners have a year assigned and a generated client code."""
        for partner in self:
            partner_sudo = partner.sudo()
            year = partner.client_year or partner._default_client_year()
            vals = {}
            if not partner.client_year:
                vals["client_year"] = year
            if not partner.code or partner.code == "/":
                vals["code"] = partner._generate_partner_code(year)
            if vals:
                partner_sudo.write(vals)
        return self

    def _get_client_code(self):
        self.ensure_one()
        self.ensure_client_code()
        if not self.code or self.code == "/":
            raise UserError(_("Unable to compute a client code for %s.") % self.display_name)
        return self.code

    def _generate_partner_code(self, year):
        short_year = str(year)[-2:]
        prefix = f"{short_year}/"
        partner_model = self.env["res.partner"].with_context(active_test=False).sudo()
        last_partner = partner_model.search(
            [("code", "like", f"{prefix}%")],
            order="code desc",
            limit=1,
        )
        next_number = 1
        if last_partner and last_partner.code:
            try:
                next_number = int(last_partner.code.split("/")[-1]) + 1
            except (ValueError, IndexError):
                next_number = 1
        return f"{prefix}{next_number:03d}"

    def _update_code_for_year_change(self):
        self.ensure_one()
        year = self.client_year
        if not year:
            return
        short_year = str(int(year))[-2:]
        prefix = f"{short_year}/"
        suffix = ""
        if self.code and "/" in self.code:
            suffix = self.code.split("/")[-1]
        if suffix.isdigit():
            new_code = f"{prefix}{suffix.zfill(3)}"
        else:
            new_code = self._generate_partner_code(year)
        self.with_context(skip_year_sync=True).write({"code": new_code})

class ContactAttachments(models.Model):
    _name = "contact.attachments"

    name = fields.Char(string="Name")
    blue_image = fields.Image("Blue Image", max_width=1024, max_height=1024)
    qatar_id = fields.Char(string="Qatar ID")
    commercial_register = fields.Char(string="Commercial Register")
    partner_id = fields.Many2one("res.partner", string="Partner", index=True)


class QlkClientDocument(models.Model):
    _name = "qlk.client.document"
    _description = "Client Document"
    _order = "partner_id, doc_type"

    DOC_SELECTION = [
        ("company_commercial_register", "Commercial Registration"),
        ("company_trade_license", "Trade License"),
        ("company_poa", "Company Power of Attorney"),
        ("company_owner_id", "Owner ID Copy"),
        ("individual_id", "Personal ID"),
        ("individual_poa", "Personal Power of Attorney"),
    ]

    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, ondelete="cascade", index=True
    )
    doc_type = fields.Selection(selection=DOC_SELECTION, string="Document Type", required=True, index=True)
    # attachment_id = fields.Many2one("ir.attachment", string="Attachment", ondelete="set null", index=True)
    is_uploaded = fields.Boolean(string="Uploaded")
    poa_expiration_date = fields.Date(string="POA Expiration Date")
    poa_reference = fields.Char(string="Reference / Number")
    note = fields.Text(string="Notes")

    _sql_constraints = [
        ("partner_doc_unique", "unique(partner_id, doc_type)", "Each document type can only be added once per client.")
    ]

    # ------------------------------------------------------------------------------
    # دالة تحدد إذا ما كان هناك مرفق فعلي لكل مستند لتسهيل التنبيهات.
    # ------------------------------------------------------------------------------


class RequestContact(models.Model):
    _name = "request.contact"

    name = fields.Char(string="Description")
    partner_id = fields.Many2one("res.partner", string="Client", index=True)
    new_client = fields.Char(string="New Client")
    state = fields.Selection(
        [("draft", "Draft"), ("pending", "Pending"), ("approved", "Approved"), ("cancel", "Cancel")],
        default="draft",
        string="State",
    )
    user_id = fields.Many2one(
        "res.users", string="Responsible", default=lambda res: res.env.user.id, index=True
    )
    note = fields.Html(string="Note")

    # ------------------------------------------------------------------------------
    # دالة تعيد الطلب إلى مرحلة المسودة لبدء دورة الموافقة من جديد.
    # ------------------------------------------------------------------------------
    def action_reset_to_draft(self):
        for record in self:
            record.state = "draft"

    # ------------------------------------------------------------------------------
    # دالة لنقل الطلب إلى مرحلة الانتظار حتى يراجعه المسؤول.
    # ------------------------------------------------------------------------------
    def action_pending(self):
        for record in self:
            record.state = "pending"

    # ------------------------------------------------------------------------------
    # دالة اعتماد الطلب بعد مراجعة البيانات.
    # ------------------------------------------------------------------------------
    def action_approved(self):
        for record in self:
            record.state = "approved"

    # ------------------------------------------------------------------------------
    # دالة لإلغاء الطلب في حال عدم الحاجة له.
    # ------------------------------------------------------------------------------
    def action_cancel(self):
        for record in self:
            record.state = "cancel"

    def _ensure_same_company_than_tasks(self):
        return True
