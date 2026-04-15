# -*- coding: utf-8 -*-
import base64
from io import BytesIO

from odoo import _, fields, models


class BDReportXlsx(models.AbstractModel):
    _name = "report.qlk_management.bd_report_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "BD Proposals and Engagement Letters XLSX Report"

    # -------------------------------------------------------------------------
    # Public API: generate a business-ready workbook with separate sheets for
    # proposals and engagement letters, while keeping one shared column layout.
    # -------------------------------------------------------------------------
    def generate_xlsx_report(self, workbook, data, records):
        company = self.env.company
        wizard = records[:1]
        payload = (
            wizard._get_report_payload(data=data)
            if wizard
            else self.env["bd.report.wizard"]._get_report_payload_from_data(data=data)
        )
        formats = self._get_formats(workbook)
        if payload["record_type"] in ("proposal", "both"):
            self._write_sheet(
                workbook=workbook,
                company=company,
                sheet_name=_("Proposals"),
                title=_("BD Report - Proposals"),
                rows=payload["proposal_rows"],
                formats=formats,
                date_from=payload["date_from"],
                date_to=payload["date_to"],
            )
        if payload["record_type"] in ("engagement", "both"):
            self._write_sheet(
                workbook=workbook,
                company=company,
                sheet_name=_("Engagement Letters"),
                title=_("BD Report - Engagement Letters"),
                rows=payload["engagement_rows"],
                formats=formats,
                date_from=payload["date_from"],
                date_to=payload["date_to"],
            )

    def _get_amount_format(self, workbook, formats, currency_symbol, total=False):
        cache_key = "total_amount_cache" if total else "amount_cache"
        cache = formats.setdefault(cache_key, {})
        symbol = (currency_symbol or "").strip()
        if symbol not in cache:
            format_vals = {
                "border": 1,
                "num_format": f'"{symbol}" #,##0.00' if symbol else "#,##0.00",
            }
            if total:
                format_vals.update(
                    {
                        "bold": True,
                        "bg_color": "#EAEFF3",
                    }
                )
            cache[symbol] = workbook.add_format(format_vals)
        return cache[symbol]

    def _write_sheet(self, workbook, company, sheet_name, title, rows, formats, date_from, date_to):
        worksheet = workbook.add_worksheet(sheet_name[:31])
        worksheet.freeze_panes(7, 0)
        worksheet.set_zoom(90)
        worksheet.set_column("A:A", 24)
        worksheet.set_column("B:B", 28)
        worksheet.set_column("C:C", 16)
        worksheet.set_column("D:D", 18)
        worksheet.set_column("E:E", 18)
        worksheet.set_column("F:F", 16)
        worksheet.set_column("G:G", 22)
        worksheet.set_column("H:H", 18)
        worksheet.set_column("I:K", 16)
        worksheet.set_column("L:L", 16)
        worksheet.set_column("M:M", 10)

        self._insert_company_logo(worksheet, company)
        worksheet.merge_range("B1:M2", title, formats["title"])
        worksheet.write("B3", company.display_name or "", formats["subtitle"])
        worksheet.write(
            "B4",
            _("From: %(date_from)s  To: %(date_to)s") % {
                "date_from": fields.Date.to_string(date_from),
                "date_to": fields.Date.to_string(date_to),
            },
            formats["subtitle"],
        )
        worksheet.write("B5", fields.Date.context_today(self), formats["subtitle"])

        headers = [
            _("Sequence / Reference"),
            _("Client Name"),
            _("Client Code"),
            _("Service Type"),
            _("Contract Type"),
            _("Billing Type"),
            _("Assigned Lawyer"),
            _("Assignment Date"),
            _("Total Legal Fees"),
            _("Paid Amount"),
            _("Unpaid Amount"),
            _("Payment Status"),
            _("Currency"),
        ]
        header_row = 6
        for column, header in enumerate(headers):
            worksheet.write(header_row, column, header, formats["header"])

        row_index = header_row + 1
        totals_by_currency = {}
        for index, row in enumerate(rows):
            line_format = formats["row_alt"] if index % 2 else formats["row"]
            amount_format = self._get_amount_format(workbook, formats, row["currency_symbol"])
            worksheet.write(row_index, 0, row["reference"], line_format)
            worksheet.write(row_index, 1, row["client_name"], line_format)
            worksheet.write(row_index, 2, row["client_code"], line_format)
            worksheet.write(row_index, 3, row["service_type"], line_format)
            worksheet.write(row_index, 4, row["contract_type"], line_format)
            worksheet.write(row_index, 5, row["billing_type"], line_format)
            worksheet.write(row_index, 6, row["assigned_lawyer"], line_format)
            if row["assignment_date"]:
                worksheet.write_datetime(
                    row_index,
                    7,
                    fields.Datetime.to_datetime(row["assignment_date"]),
                    formats["date"],
                )
            else:
                worksheet.write(row_index, 7, "", line_format)
            worksheet.write_number(row_index, 8, row["total_legal_fees"], amount_format)
            worksheet.write_number(row_index, 9, row["paid_amount"], amount_format)
            worksheet.write_number(row_index, 10, row["unpaid_amount"], amount_format)
            worksheet.write(row_index, 11, row["payment_status"], line_format)
            worksheet.write(row_index, 12, row["currency_name"], line_format)

            currency_key = row["currency_name"] or _("N/A")
            totals = totals_by_currency.setdefault(
                currency_key,
                {
                    "fees": 0.0,
                    "paid": 0.0,
                    "unpaid": 0.0,
                    "currency_symbol": row["currency_symbol"],
                },
            )
            totals["fees"] += row["total_legal_fees"]
            totals["paid"] += row["paid_amount"]
            totals["unpaid"] += row["unpaid_amount"]
            row_index += 1

        row_index += 1
        worksheet.write(row_index, 0, _("Totals By Currency"), formats["total_label"])
        row_index += 1
        for currency_name, totals in sorted(totals_by_currency.items()):
            total_amount_format = self._get_amount_format(
                workbook,
                formats,
                totals.get("currency_symbol"),
                total=True,
            )
            worksheet.write(row_index, 0, currency_name, formats["total_label"])
            worksheet.write(row_index, 7, _("Total Legal Fees"), formats["total_label"])
            worksheet.write_number(row_index, 8, totals["fees"], total_amount_format)
            worksheet.write(row_index, 9, _("Total Paid"), formats["total_label"])
            worksheet.write_number(row_index, 10, totals["paid"], total_amount_format)
            worksheet.write(row_index, 11, _("Total Unpaid"), formats["total_label"])
            worksheet.write_number(row_index, 12, totals["unpaid"], total_amount_format)
            row_index += 1

    def _insert_company_logo(self, worksheet, company):
        if not company.logo:
            return
        image_stream = BytesIO(base64.b64decode(company.logo))
        worksheet.insert_image(
            "A1",
            "company_logo.png",
            {
                "image_data": image_stream,
                "x_scale": 0.4,
                "y_scale": 0.4,
                "x_offset": 4,
                "y_offset": 4,
            },
        )

    def _get_formats(self, workbook):
        return {
            "title": workbook.add_format(
                {
                    "bold": True,
                    "font_size": 16,
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "subtitle": workbook.add_format(
                {
                    "font_size": 10,
                    "italic": True,
                    "color": "#52616B",
                }
            ),
            "header": workbook.add_format(
                {
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                    "bg_color": "#D9EAF4",
                    "border": 1,
                }
            ),
            "row": workbook.add_format({"border": 1}),
            "row_alt": workbook.add_format({"border": 1, "bg_color": "#F7F9FB"}),
            "date": workbook.add_format(
                {
                    "border": 1,
                    "num_format": "yyyy-mm-dd",
                }
            ),
            "total_label": workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#EAEFF3",
                    "border": 1,
                }
            ),
            "amount_cache": {},
            "total_amount_cache": {},
        }
