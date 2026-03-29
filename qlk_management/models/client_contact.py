# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# موديلات داعمة لإدارة بيانات العملاء:
# 1) تصنيف جهة الاتصال عبر قائمة قابلة للتوسع.
# 2) قنوات تواصل متعددة للشركات (أرقام/إيميلات متعددة).
# ------------------------------------------------------------------------------
from odoo import api, fields, models, _
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
