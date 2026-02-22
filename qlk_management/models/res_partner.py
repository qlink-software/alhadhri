# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديول إدارة بيانات العملاء (Clients)
# يوفر هذا الملف جميع الحقول المساعدة للمرفقات وتحذيرات المستندات وتنبيهات
# انتهاء صلاحية التوكيلات بالإضافة إلى كود العميل بعد توقيع اتفاقية EL.
# ------------------------------------------------------------------------------
from datetime import datetime

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
    proposal_count = fields.Integer(string="Proposals", compute="_compute_related_counts")
    engagement_count = fields.Integer(string="Engagement Letters", compute="_compute_related_counts")
    project_count = fields.Integer(string="Projects", compute="_compute_related_counts")


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
#بداية 
    # @api.constrains("phone", "mobile", "email")
    # def _check_contact_channels(self):
    #     for partner in self:
    #         if partner.customer_rank <= 0:
    #             continue
    #         missing = []
    #         if not partner.mobile:
    #             missing.append(_("Mobile"))
    #         if not partner.email:
    #             missing.append(_("Email"))
    #         if missing:
    #             raise ValidationError(
    #                 _("The following fields are required for clients: %s") % ", ".join(missing)
    #             )

    # @api.constrains("email", "mobile")
    # def _check_unique_contact_fields(self):
    #     partner_model = self.env["res.partner"].sudo()
    #     for partner in self:
    #         duplicates = []
    #         if partner.email:
    #             duplicate_email = partner_model.search(
    #                 [("email", "=", partner.email), ("id", "!=", partner.id)], limit=1
    #             )
    #             if duplicate_email:
    #                 duplicates.append(_("Email"))
    #         if partner.mobile:
    #             duplicate_mobile = partner_model.search(
    #                 [("mobile", "=", partner.mobile), ("id", "!=", partner.id)], limit=1
    #             )
    #             if duplicate_mobile:
    #                 duplicates.append(_("Mobile"))
    #         if duplicates:
    #             raise UserError(
    #                 _("The following contact fields must be unique across partners: %s.")
    #                 % ", ".join(duplicates)
    #             )
#نهاية 
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
            if self._should_generate_partner_ref(vals):
                vals["ref"] = self._next_partner_ref()
        records = super().create(vals_list)
        # NOTE: Hours enforcement is temporarily disabled. Re-enable when required.
        # records._check_hours_logged()
        return records

    @staticmethod
    def _should_generate_partner_ref(vals):
        if vals.get("ref"):
            return False
        if vals.get("is_company") is False:
            return True
        if vals.get("company_type") and vals.get("company_type") != "company":
            return True
        return vals.get("customer_rank", 0) > 0

    def _next_partner_ref(self):
        yy = datetime.now().strftime("%y")
        sequence_code = self._create_sequence_for_current_year(yy)
        return self.env["ir.sequence"].next_by_code(sequence_code)

    def _create_sequence_for_current_year(self, yy):
        sequence_code = f"res.partner.sequence.{yy}"
        sequence_model = self.env["ir.sequence"].sudo()
        company_id = self.env.company.id
        sequence = sequence_model.search(
            [("code", "=", sequence_code), ("company_id", "=", company_id)],
            limit=1,
        )
        if not sequence:
            sequence_model.create(
                {
                    "name": f"Partner Ref {yy}",
                    "code": sequence_code,
                    "prefix": f"{yy}/",
                    "padding": 3,
                    "implementation": "no_gap",
                    "company_id": company_id,
                }
            )
        return sequence_code

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
        if "code" in vals and not self.env.context.get("skip_related_sync"):
            for partner in self:
                partner._sync_related_client_codes()
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

    def _compute_related_counts(self):
        proposal_counts = {}
        engagement_counts = {}
        project_counts = {}
        partner_ids = self.ids
        if partner_ids:
            proposal_groups = self.env["bd.proposal"].read_group(
                [("partner_id", "in", partner_ids)], ["partner_id"], ["partner_id"]
            )
            engagement_groups = self.env["bd.engagement.letter"].read_group(
                [("partner_id", "in", partner_ids)], ["partner_id"], ["partner_id"]
            )
            project_groups = self.env["project.project"].read_group(
                [("partner_id", "in", partner_ids)], ["partner_id"], ["partner_id"]
            )
            proposal_counts = {
                data["partner_id"][0]: (data.get("__count") or data.get("partner_id_count", 0))
                for data in proposal_groups
                if data.get("partner_id")
            }
            engagement_counts = {
                data["partner_id"][0]: (data.get("__count") or data.get("partner_id_count", 0))
                for data in engagement_groups
                if data.get("partner_id")
            }
            project_counts = {
                data["partner_id"][0]: (data.get("__count") or data.get("partner_id_count", 0))
                for data in project_groups
                if data.get("partner_id")
            }
        for partner in self:
            partner.proposal_count = proposal_counts.get(partner.id, 0)
            partner.engagement_count = engagement_counts.get(partner.id, 0)
            partner.project_count = project_counts.get(partner.id, 0)

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

    def action_view_bd_proposals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Proposals"),
            "res_model": "bd.proposal",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
                "default_client_id": self.id,
            },
        }

    def action_view_bd_engagements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Engagement Letters"),
            "res_model": "bd.engagement.letter",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
                "default_client_id": self.id,
            },
        }

    def action_view_partner_projects(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Projects"),
            "res_model": "project.project",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
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
        self.with_context(skip_year_sync=True, skip_related_sync=True).write({"code": new_code})
        self._sync_related_client_codes()

    def _sync_related_client_codes(self):
        proposals = self.env["bd.proposal"].sudo().search([("partner_id", "=", self.id)])
        if proposals:
            proposals._sync_client_code_from_partner()
        letters = self.env["bd.engagement.letter"].sudo().search([("partner_id", "=", self.id)])
        if letters:
            letters._sync_client_code_from_partner()
        projects = self.env["project.project"].sudo().search([("partner_id", "=", self.id)])
        if projects:
            projects._sync_client_code_from_partner()

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
    _order = "create_date desc, id desc"

    DOCUMENT_SELECTION = [
        ("contract", "Contract"),
        ("proposal", "Proposal"),
        ("id", "ID"),
        ("court_document", "Court Document"),
        ("power_of_attorney", "Power of Attorney"),
        ("translation", "Translation"),
        ("other", "Other"),
    ]

    name = fields.Char(string="Title", required=True)
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, ondelete="cascade", index=True
    )
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Attachment",
        required=True,
        ondelete="cascade",
        index=True,
    )
    document_type = fields.Selection(
        selection=DOCUMENT_SELECTION, string="Document Type", required=True, index=True
    )
    needs_translation = fields.Boolean(string="Needs Translation")
    is_translated = fields.Boolean(string="Translated")
    related_model = fields.Char(string="Related Model", readonly=True, copy=False)
    related_res_id = fields.Integer(string="Related Record ID", readonly=True, copy=False)
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True)
    preview_url = fields.Char(string="Preview URL", compute="_compute_preview")
    preview_html = fields.Html(string="Preview", compute="_compute_preview", sanitize=False)

    @api.depends("attachment_id", "attachment_id.mimetype")
    def _compute_preview(self):
        for doc in self:
            doc.preview_url = False
            doc.preview_html = False
            attachment = doc.attachment_id
            if not attachment:
                continue
            url = f"/web/content/{attachment.id}?download=0"
            doc.preview_url = url
            mimetype = attachment.mimetype or ""
            if mimetype.startswith("image/"):
                doc.preview_html = (
                    f'<img src="{url}" style="max-width: 100%; height: auto;" />'
                )
            else:
                doc.preview_html = (
                    f'<iframe src="{url}" style="width: 100%; min-height: 480px; border: 0;"></iframe>'
                )

    @api.model_create_multi
    def create(self, vals_list):
        Attachment = self.env["ir.attachment"].sudo()
        for vals in vals_list:
            if not vals.get("name") and vals.get("attachment_id"):
                attachment = Attachment.browse(vals["attachment_id"])
                vals["name"] = attachment.name or _("Client Document")
        records = super().create(vals_list)
        records._sync_attachment()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "attachment_id" in vals or "partner_id" in vals:
            self._sync_attachment()
        return res

    def _sync_attachment(self):
        for doc in self:
            if not doc.attachment_id:
                continue
            vals = {"public": False}
            if doc.partner_id:
                vals.update({"res_model": "res.partner", "res_id": doc.partner_id.id})
            doc.attachment_id.sudo().write(vals)

    def action_preview(self):
        self.ensure_one()
        if not self.attachment_id:
            return False
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.attachment_id.id}?download=0",
            "target": "new",
        }


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
