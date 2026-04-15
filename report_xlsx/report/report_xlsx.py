# -*- coding: utf-8 -*-
from odoo import models


class ReportXlsxAbstract(models.AbstractModel):
    """Base abstract model used by XLSX report implementations."""

    _name = "report.report_xlsx.abstract"
    _description = "Abstract XLSX Report"

    def _get_workbook_options(self):
        """Use in-memory workbooks by default to keep report rendering simple."""
        return {"in_memory": True}

    def generate_xlsx_report(self, workbook, data, records):
        raise NotImplementedError("Subclasses must implement generate_xlsx_report().")


# Compatibility alias for modules importing the historical class path.
ReportXlsx = ReportXlsxAbstract
