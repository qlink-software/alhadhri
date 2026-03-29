from odoo import http
from odoo.http import request


class RecruitmentDocumentApprovalController(http.Controller):

    def _get_package(self, token):
        if not token:
            return request.env["hr.recruitment.document.package"]
        return request.env["hr.recruitment.document.package"].sudo().search([("access_token", "=", token)], limit=1)

    @http.route("/recruitment/document/approve/<string:token>", type="http", auth="public", website=False, csrf=False)
    def approve_document(self, token, **kwargs):
        package = self._get_package(token)
        if not package:
            return request.make_response("<h3>Invalid approval link.</h3>")

        package.action_employee_accept()
        return request.make_response("<h3>Documents approved successfully. Your system credentials have been emailed.</h3>")

    @http.route("/recruitment/document/reject/<string:token>", type="http", auth="public", website=False, csrf=False)
    def reject_document(self, token, **kwargs):
        package = self._get_package(token)
        if not package:
            return request.make_response("<h3>Invalid rejection link.</h3>")

        package.action_employee_reject()
        return request.make_response("<h3>Documents were rejected. HR team has been notified.</h3>")
