# -*- coding: utf-8 -*-
from io import BytesIO

from odoo import _, fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:  # pragma: no cover - enforced by manifest dependency
    xlsxwriter = None


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    report_type = fields.Selection(
        selection_add=[("xlsx", "XLSX")],
        ondelete={"xlsx": "set default"},
    )

    def _render_xlsx(self, report_ref, res_ids, data=None):
        """Render an XLSX report using the abstract report model."""
        if xlsxwriter is None:
            raise UserError(_("The Python library 'xlsxwriter' is required to generate XLSX reports."))

        report = self._get_report(report_ref)
        report_model_name = f"report.{report.report_name}"
        report_model = self.env.get(report_model_name)
        if report_model is None:
            raise UserError(
                _("The XLSX report model '%s' could not be found.", report_model_name)
            )

        if not res_ids:
            active_model = self.env.context.get("active_model")
            active_ids = self.env.context.get("active_ids") or []
            if active_model == report.model and active_ids:
                res_ids = active_ids

        output = BytesIO()
        workbook = xlsxwriter.Workbook(
            output,
            report_model._get_workbook_options(),
        )
        records = self.env[report.model].browse(res_ids or [])
        report_model.generate_xlsx_report(workbook, data or {}, records)
        workbook.close()
        output.seek(0)
        return output.read(), "xlsx"

    def _get_readable_fields(self):
        return super()._get_readable_fields() | {"report_file"}
