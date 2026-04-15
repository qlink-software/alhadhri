from odoo import http
from odoo.exceptions import UserError
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

        try:
            package.action_sign()
        except UserError as error:
            return request.make_response(f"<h3>{error.args[0]}</h3>")
        return request.make_response("<h3>Documents signed successfully. Your system credentials have been emailed.</h3>")

    @http.route("/recruitment/document/reject/<string:token>", type="http", auth="public", website=False, csrf=False)
    def reject_document(self, token, **kwargs):
        package = self._get_package(token)
        if not package:
            return request.make_response("<h3>Invalid rejection link.</h3>")

        try:
            package.action_employee_reject()
        except UserError as error:
            return request.make_response(f"<h3>{error.args[0]}</h3>")
        return request.make_response("<h3>Documents were rejected. HR team has been notified.</h3>")
