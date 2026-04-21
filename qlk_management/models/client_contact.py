# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديلات داعمة لإدارة بيانات العملاء:
# 1) تصنيف جهة الاتصال عبر قائمة قابلة للتوسع.
# 2) قنوات تواصل متعددة للشركات (أرقام/إيميلات متعددة).
# ------------------------------------------------------------------------------
import re

from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError


class QlkContactClassification(models.Model):
    _name = "qlk.contact.classification"
    _description = "Contact Classification"
    _order = "sequence, name"

    # هذا الاسم يظهر في قائمة التصنيفات داخل بطاقة العميل.
    name = fields.Char(string="Classification", required=True, translate=True)
    # هذا الحقل يحدد ترتيب ظهور التصنيفات في القائمة.
    sequence = fields.Integer(string="Sequence", default=10)
    # هذا الحقل يسمح بإخفاء التصنيف بدون حذفه.
    active = fields.Boolean(default=True)


class QlkCompanyContactChannel(models.Model):
    _name = "qlk.company.contact.channel"
    _description = "Company Contact Channel"
    _order = "sequence, id"

    CHANNEL_SELECTION = [
        ("phone", "Phone"),
        ("email", "Email"),
    ]

    # هذا الربط يحدد الشركة المالكة لقناة التواصل.
    partner_id = fields.Many2one(
        "res.partner",
        string="Company",
        required=True,
        ondelete="cascade",
        index=True,
    )
    # هذا الحقل يحدد نوع القناة (هاتف أو بريد إلكتروني).
    channel_type = fields.Selection(
        selection=CHANNEL_SELECTION,
        string="Channel Type",
        required=True,
        default="phone",
    )
    # هذا الحقل يخزن قيمة القناة (رقم/إيميل).
    value = fields.Char(string="Value", required=True)
    # هذا الحقل اختياري لإضافة وصف قصير للقناة.
    label = fields.Char(string="Label")
    # هذا الحقل يحدد ترتيب القنوات داخل بطاقة الشركة.
    sequence = fields.Integer(string="Sequence", default=10)

    _sql_constraints = [
        (
            "qlk_company_contact_channel_unique",
            "unique(partner_id, channel_type, value)",
            "The same contact channel already exists for this company.",
        ),
    ]

    # هذه القاعدة تمنع ربط قنوات التواصل بسجل فردي وتسمح فقط للشركات.
    @api.constrains("partner_id")
    def _check_company_partner(self):
        for record in self:
            if record.partner_id and record.partner_id.company_type != "company":
                raise ValidationError(_("Contact channels are available for companies only."))

    # هذه القاعدة تتحقق من شكل البريد الإلكتروني عند اختيار نوع Email.
    @api.constrains("channel_type", "value")
    def _check_email_format(self):
        for record in self:
            if record.channel_type != "email" or not record.value:
                continue
            if "@" not in record.value:
                raise ValidationError(_("Please enter a valid email address."))


class ResPartnerContactInfo(models.Model):
    _name = "res.partner.contact.info"
    _description = "Partner Contact Information"
    _order = "sequence, id"

    CONTACT_SELECTION = [
        ("mobile", "Mobile"),
        ("email", "Email"),
    ]
    _mobile_pattern = re.compile(r"^[+0-9][0-9().\-\s]{5,}$")

    # هذا الربط يحدد العميل/الشركة المالكة لبيانات التواصل الإضافية.
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="cascade",
        index=True,
    )
    # هذا الحقل يحدد هل السطر يمثل جوالًا أو بريدًا إلكترونيًا.
    contact_type = fields.Selection(
        selection=CONTACT_SELECTION,
        string="Contact Type",
        required=True,
        default="mobile",
    )
    # هذا الحقل يخزن القيمة الفعلية للجوال أو البريد الإلكتروني.
    value = fields.Char(string="Value", required=True)
    # هذا الحقل يحدد السطر الرئيسي الذي تتم مزامنته مع الحقول الأساسية في الشريك.
    is_primary = fields.Boolean(string="Primary")
    # هذا الحقل يحدد ترتيب عرض القنوات داخل النموذج.
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "res_partner_contact_info_unique",
            "unique(partner_id, contact_type, value)",
            "The same contact info already exists for this partner.",
        ),
    ]

    def _table_exists(self, table_name):
        self.env.cr.execute(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM information_schema.tables
                 WHERE table_schema = ANY (current_schemas(FALSE))
                   AND table_name = %s
            )
            """,
            (table_name,),
        )
        return bool(self.env.cr.fetchone()[0])

    def init(self):
        # هذا التحديث ينقل بيانات القنوات القديمة إلى النموذج الجديد بدون فقدان أي بيانات.
        # أثناء التثبيت الأول قد يستدعي Odoo init قبل إنشاء جدول الموديل نفسه، لذلك لا ننفذ
        # أي إدخال إلا بعد التأكد من وجود كل الجداول المطلوبة.
        if not self._table_exists(self._table):
            return
        if not self._table_exists("qlk_company_contact_channel"):
            return
        if not self._table_exists("res_partner"):
            return
        self.env.cr.execute(
            """
            INSERT INTO res_partner_contact_info (
                partner_id, contact_type, value, is_primary, sequence, active,
                create_uid, create_date, write_uid, write_date
            )
            SELECT
                old.partner_id,
                CASE old.channel_type
                    WHEN 'phone' THEN 'mobile'
                    ELSE 'email'
                END,
                old.value,
                CASE
                    WHEN old.channel_type = 'email' AND old.value = partner.email THEN TRUE
                    WHEN old.channel_type = 'phone' AND old.value = partner.mobile THEN TRUE
                    ELSE FALSE
                END,
                COALESCE(old.sequence, 10),
                TRUE,
                old.create_uid,
                old.create_date,
                old.write_uid,
                old.write_date
            FROM qlk_company_contact_channel old
            JOIN res_partner partner
              ON partner.id = old.partner_id
            WHERE NOT EXISTS (
                SELECT 1
                  FROM res_partner_contact_info new_info
                 WHERE new_info.partner_id = old.partner_id
                   AND new_info.contact_type = CASE
                        WHEN old.channel_type = 'phone' THEN 'mobile'
                        ELSE 'email'
                   END
                   AND new_info.value = old.value
            )
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = [self._prepare_contact_info_vals(vals) for vals in vals_list]
        records = super().create(prepared_vals_list)
        records._ensure_single_primary()
        records.mapped("partner_id")._sync_primary_contact_info_fields()
        return records

    def write(self, vals):
        vals = self._prepare_contact_info_vals(vals)
        res = super().write(vals)
        self._ensure_single_primary()
        self.mapped("partner_id")._sync_primary_contact_info_fields()
        return res

    def unlink(self):
        partners = self.mapped("partner_id")
        res = super().unlink()
        partners._sync_primary_contact_info_fields()
        return res

    @api.model
    def _prepare_contact_info_vals(self, vals):
        vals = dict(vals)
        value = vals.get("value")
        if isinstance(value, str):
            value = value.strip()
            if vals.get("contact_type") == "email":
                value = value.lower()
            vals["value"] = value
        return vals

    def _ensure_single_primary(self):
        for partner in self.mapped("partner_id"):
            for contact_type in ("mobile", "email"):
                primary_lines = partner.contact_info_ids.filtered(
                    lambda line: line.contact_type == contact_type and line.is_primary
                ).sorted(lambda line: (line.sequence, line.id))
                if len(primary_lines) > 1:
                    primary_lines[1:].write({"is_primary": False})

    @api.constrains("value")
    def _check_value_not_empty(self):
        for record in self:
            if not (record.value or "").strip():
                raise ValidationError(_("Contact value cannot be empty."))

    @api.constrains("contact_type", "value")
    def _check_contact_value_format(self):
        for record in self:
            value = (record.value or "").strip()
            if not value:
                continue
            if record.contact_type == "email":
                if not tools.single_email_re.match(value):
                    raise ValidationError(_("Please enter a valid email address."))
                continue
            digits_count = len(re.sub(r"\D", "", value))
            if digits_count < 6 or not self._mobile_pattern.match(value):
                raise ValidationError(_("Please enter a valid mobile number."))

    @api.constrains("partner_id", "contact_type", "is_primary")
    def _check_single_primary_per_type(self):
        for record in self:
            if not record.is_primary:
                continue
            duplicates = record.partner_id.contact_info_ids.filtered(
                lambda line: line.id != record.id
                and line.contact_type == record.contact_type
                and line.is_primary
            )
            if duplicates:
                raise ValidationError(
                    _("Only one primary contact is allowed for each contact type.")
                )


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ------------------------------------------------------------------------------
    # هذه الدالة تزامن الجوال/البريد الأساسي من الجدول الجديد إلى حقول الشريك الأساسية.
    # ------------------------------------------------------------------------------
    def _sync_primary_contact_info_fields(self):
        for partner in self:
            primary_mobile = partner.contact_info_ids.filtered(
                lambda line: line.contact_type == "mobile" and line.is_primary
            )[:1]
            primary_email = partner.contact_info_ids.filtered(
                lambda line: line.contact_type == "email" and line.is_primary
            )[:1]
            vals = {}
            if primary_mobile:
                vals["mobile"] = primary_mobile.value
                if partner.company_type == "company" and not partner.phone:
                    vals["phone"] = primary_mobile.value
            if primary_email:
                vals["email"] = primary_email.value
            if vals:
                partner.with_context(
                    skip_client_partner_security=True,
                    skip_contact_info_partner_sync=True,
                ).write(vals)
