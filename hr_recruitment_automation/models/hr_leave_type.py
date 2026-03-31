from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    # هذا الحقل يميز أنواع الإجازات المرتبطة بسياسات الأتمتة داخل هذا الموديول.
    automation_code = fields.Char(string="Automation Code", index=True, copy=False)
    # حقل توافق خلفي لأن بعض العروض الموروثة في قاعدة البيانات ما زالت تشير إليه.
    overtime_deductible = fields.Boolean(
        string="Overtime Deductible",
        help="Indicates whether this time off type can be deducted from overtime balances.",
        default=False,
    )
