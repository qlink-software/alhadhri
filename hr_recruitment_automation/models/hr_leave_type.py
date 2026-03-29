from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    # هذا الحقل يميز أنواع الإجازات المرتبطة بسياسات الأتمتة داخل هذا الموديول.
    automation_code = fields.Char(string="Automation Code", index=True, copy=False)
