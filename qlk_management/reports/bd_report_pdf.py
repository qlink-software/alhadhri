# -*- coding: utf-8 -*-
from odoo import models


class BDReportPdf(models.AbstractModel):
    _name = "report.qlk_management.bd_report_pdf_document"
    _description = "BD Unified PDF Report"

    def _get_report_values(self, docids, data=None):
        wizard = self.env["bd.report.wizard"].browse(docids[:1]).exists()
        payload = (
            wizard._get_report_payload(data=data)
            if wizard
            else self.env["bd.report.wizard"]._get_report_payload_from_data(data=data)
        )
        return {
            "doc_ids": wizard.ids,
            "doc_model": "bd.report.wizard",
            "docs": wizard,
            "report_data": payload,
            "company": self.env.company,
        }
