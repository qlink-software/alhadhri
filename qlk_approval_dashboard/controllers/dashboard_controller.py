# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class ApprovalDashboardController(http.Controller):
    @http.route("/qlk_approval_dashboard/data", type="json", auth="user")
    def get_dashboard_data(self, **kwargs):
        return request.env["qlk.approval.dashboard"].get_dashboard_data(**kwargs)

    @http.route("/qlk_approval_dashboard/pending_count", type="json", auth="user")
    def get_pending_count(self):
        return request.env["qlk.approval.dashboard"].get_pending_count()
