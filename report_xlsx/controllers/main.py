# -*- coding: utf-8 -*-
import json
import logging

import werkzeug.exceptions
from werkzeug.urls import url_parse

from odoo import http
from odoo.http import content_disposition, request
from odoo.tools.misc import html_escape
from odoo.tools.safe_eval import safe_eval, time

from odoo.addons.web.controllers.report import ReportController

_logger = logging.getLogger(__name__)


class ReportControllerXlsx(ReportController):
    """Extend the standard report controller with XLSX rendering support."""

    @http.route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        if converter != "xlsx":
            return super().report_routes(reportname, docids=docids, converter=converter, **data)

        report = request.env["ir.actions.report"]
        context = dict(request.env.context)

        if docids:
            docids = [int(docid) for docid in docids.split(",") if docid.isdigit()]
        if data.get("options"):
            data.update(json.loads(data.pop("options")))
        if data.get("context"):
            data["context"] = json.loads(data["context"])
            context.update(data["context"])

        xlsx_content = report.with_context(context)._render_xlsx(reportname, docids, data=data)[0]
        headers = [
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Length", len(xlsx_content)),
        ]
        return request.make_response(xlsx_content, headers=headers)

    @http.route()
    def report_download(self, data, context=None, token=None, readonly=True):
        request_content = json.loads(data)
        url, report_type = request_content[0], request_content[1]

        if report_type != "xlsx":
            return super().report_download(data, context=context, token=token, readonly=readonly)

        reportname = "???"
        try:
            pattern = "/report/xlsx/"
            reportname = url.split(pattern)[1].split("?")[0]

            docids = None
            if "/" in reportname:
                reportname, docids = reportname.split("/")

            if docids:
                response = self.report_routes(reportname, docids=docids, converter="xlsx", context=context)
            else:
                data = url_parse(url).decode_query(cls=dict)
                if "context" in data:
                    context, data_context = json.loads(context or "{}"), json.loads(data.pop("context"))
                    context = json.dumps({**context, **data_context})
                response = self.report_routes(reportname, converter="xlsx", context=context, **data)

            report = request.env["ir.actions.report"]._get_report_from_name(reportname)
            filename = f"{report.name}.xlsx"
            if docids:
                ids = [int(value) for value in docids.split(",") if value.isdigit()]
                obj = request.env[report.model].browse(ids)
                if report.print_report_name and len(obj) == 1:
                    report_name = safe_eval(report.print_report_name, {"object": obj, "time": time})
                    filename = f"{report_name}.xlsx"

            response.headers.add("Content-Disposition", content_disposition(filename))
            return response
        except Exception as error:
            _logger.warning("Error while generating XLSX report %s", reportname, exc_info=True)
            serialized_error = http.serialize_exception(error)
            payload = {
                "code": 200,
                "message": "Odoo Server Error",
                "data": serialized_error,
            }
            response = request.make_response(html_escape(json.dumps(payload)))
            raise werkzeug.exceptions.InternalServerError(response=response) from error
