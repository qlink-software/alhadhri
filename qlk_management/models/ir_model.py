# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# توريث نموذج ir.model
# يضيف هذا الملف حماية عند حساب عدد السجلات لمنع الأخطاء في حال حذف موديلات
# من الريجستري أثناء إزالة الموديولات.
# ------------------------------------------------------------------------------
from odoo import api, models
from odoo.tools.sql import SQL


class IrModel(models.Model):
    _inherit = "ir.model"

    # ------------------------------------------------------------------------------
    # دالة تحسب عدد السجلات لكل موديل مع تجاهل الموديلات غير المتوفرة في الريجستري.
    # ------------------------------------------------------------------------------
    @api.depends()
    def _compute_count(self):
        self.count = 0
        for model in self:
            try:
                records = self.env[model.model]
            except KeyError:
                continue
            if not records._abstract and records._auto:
                [[count]] = self.env.execute_query(
                    SQL("SELECT COUNT(*) FROM %s", SQL.identifier(records._table))
                )
                model.count = count
