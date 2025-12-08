# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديول إدارة بيانات العملاء (Clients)
# يوفر هذا الملف جميع الحقول المساعدة للمرفقات وتحذيرات المستندات وتنبيهات
# انتهاء صلاحية التوكيلات بالإضافة إلى كود العميل بعد توقيع اتفاقية EL.
# ------------------------------------------------------------------------------
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    indust_date = fields.Date(string="Date")
    client_attachment_ids = fields.One2many(
        "contact.attachments", "partner_id", string="Client Attachments"
    )
    task_ids = fields.One2many("task", "crm_id", string="Working Hours")
    client_document_ids = fields.One2many(
        "qlk.client.document", "partner_id", string="Client Documents"
    )
    document_warning_message = fields.Html(compute="_compute_document_warning")
    document_warning_required = fields.Boolean(compute="_compute_document_warning")
    poa_next_expiration_date = fields.Date(
        string="Next POA Expiry", compute="_compute_poa_expiration_info", store=True
    )
    poa_expiry_reminder = fields.Char(
        string="Client POA Expiry Reminder", compute="_compute_poa_expiration_info", store=True
    )
    bd_client_code = fields.Char(string="Client Code", copy=False, readonly=True)
    bd_qid = fields.Char(string="QID / ID")
    bd_passport = fields.Char(string="Passport")
    bd_contact_details = fields.Text(string="Contact Details")

    # ------------------------------------------------------------------------------
    # دالة تحدد المستندات المطلوبة حسب نوع العميل (شركة أو فرد).
    # ------------------------------------------------------------------------------
    def _get_required_document_types(self):
        if self.company_type == "company":
            return ["company_commercial_register", "company_trade_license", "company_poa"]
        return ["individual_id", "individual_poa"]

    # ------------------------------------------------------------------------------
    # دالة تحسب تحذيرات المستندات الناقصة وتعرضها داخل بطاقة العميل.
    # ------------------------------------------------------------------------------
    @api.depends("client_document_ids", "client_document_ids.doc_type", "client_document_ids.is_uploaded")
    def _compute_document_warning(self):
        doc_model = self.env["qlk.client.document"]
        doc_labels = dict(doc_model._fields["doc_type"].selection)
        for partner in self:
            required = partner._get_required_document_types()
            available = {doc.doc_type for doc in partner.client_document_ids if doc.is_uploaded}
            missing = [doc_labels.get(doc_type, doc_type) for doc_type in required if doc_type not in available]
            if missing:
                partner.document_warning_required = True
                items = "".join(f"<li>{doc}</li>" for doc in missing)
                partner.document_warning_message = (
                    "<div class='alert alert-warning'>"
                    "<strong>Missing required client documents:</strong>"
                    f"<ul>{items}</ul>"
                    "</div>"
                )
            else:
                partner.document_warning_required = False
                partner.document_warning_message = False

    def get_missing_document_labels(self):
        """Return a list of missing required document labels for the partner."""
        self.ensure_one()
        doc_model = self.env["qlk.client.document"]
        doc_labels = dict(doc_model._fields["doc_type"].selection)
        required = self._get_required_document_types()
        available = {doc.doc_type for doc in self.client_document_ids if doc.is_uploaded}
        return [doc_labels.get(doc_type, doc_type) for doc_type in required if doc_type not in available]

    # ------------------------------------------------------------------------------
    # دالة تحسب أقرب تاريخ لانتهاء POA وتصيغ رسالة تذكير للواجهة.
    # ------------------------------------------------------------------------------
    @api.depends("client_document_ids.poa_expiration_date")
    def _compute_poa_expiration_info(self):
        today = fields.Date.context_today(self)
        for partner in self:
            upcoming_doc = False
            reminder = False
            dated_docs = [
                doc for doc in partner.client_document_ids if doc.poa_expiration_date and doc.is_uploaded
            ]
            if dated_docs:
                upcoming_doc = min(dated_docs, key=lambda doc: doc.poa_expiration_date)
            if upcoming_doc:
                partner.poa_next_expiration_date = upcoming_doc.poa_expiration_date
                delta = (upcoming_doc.poa_expiration_date - today).days
                if delta < 0:
                    reminder = _("POA is already expired since %s") % upcoming_doc.poa_expiration_date
                else:
                    reminder = _("POA expires in %s days (%s)") % (delta, upcoming_doc.poa_expiration_date)
            else:
                partner.poa_next_expiration_date = False
            partner.poa_expiry_reminder = reminder

    @api.constrains("phone", "mobile", "email")
    def _check_contact_channels(self):
        for partner in self:
            if partner.customer_rank <= 0:
                continue
            missing = []
            if not partner.phone:
                missing.append(_("Phone"))
            if not partner.mobile:
                missing.append(_("Mobile"))
            if not partner.email:
                missing.append(_("Email"))
            if missing:
                raise ValidationError(
                    _("The following fields are required for clients: %s") % ", ".join(missing)
                )


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
    attachment_id = fields.Many2one("ir.attachment", string="Attachment", ondelete="set null", index=True)
    is_uploaded = fields.Boolean(string="Uploaded", compute="_compute_is_uploaded", store=True)
    poa_expiration_date = fields.Date(string="POA Expiration Date")
    poa_reference = fields.Char(string="Reference / Number")
    note = fields.Text(string="Notes")

    _sql_constraints = [
        ("partner_doc_unique", "unique(partner_id, doc_type)", "Each document type can only be added once per client.")
    ]

    # ------------------------------------------------------------------------------
    # دالة تحدد إذا ما كان هناك مرفق فعلي لكل مستند لتسهيل التنبيهات.
    # ------------------------------------------------------------------------------
    @api.depends("attachment_id")
    def _compute_is_uploaded(self):
        for record in self:
            record.is_uploaded = bool(record.attachment_id)


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
