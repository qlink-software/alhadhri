# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# هذا الكنترولر يوفّر نقطة خروج تلقائي عند الخمول،
# مع إعادة توجيه المستخدم لصفحة الدخول ثم داشبورده الافتراضي.
# ------------------------------------------------------------------------------
from urllib.parse import quote

from odoo import http
from odoo.http import request


class QlkSessionTimeoutController(http.Controller):
    @http.route("/qlk_management/session/idle_logout", type="json", auth="user")
    def idle_logout(self):
        user = request.env.user
        dashboard_url = user.get_dashboard_redirect_url() if user else "/web"
        redirect_target = "/web/login?redirect=%s" % quote(dashboard_url, safe="")
        request.session.logout(keep_db=True)
        return {"redirect_url": redirect_target}
