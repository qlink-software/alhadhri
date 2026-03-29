# -*- coding: utf-8 -*-
from odoo import _, api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # ------------------------------------------------------------------------------
    # هذه الدالة تحدد هل المستخدم يمتلك صلاحية عرض جميع بيانات الداشبورد
    # (مثل MP أو مدير BD) أم يجب أن يرى بياناته الشخصية فقط.
    # ------------------------------------------------------------------------------
    def _qlk_can_view_all_dashboards(self):
        self.ensure_one()
        return bool(
            self.has_group("qlk_management.group_mp")
            or self.has_group("qlk_management.bd_manager_group")
        )

    # ------------------------------------------------------------------------------
    # هذه الدالة تحدد أكشن الداشبورد الافتراضي للمستخدم بعد تسجيل الدخول.
    # ------------------------------------------------------------------------------
    def _qlk_preferred_dashboard_action(self):
        self.ensure_one()
        if self.has_group("qlk_management.bd_manager_group") or self.has_group(
            "qlk_management.bd_assistant_manager_group"
        ):
            return self.env.ref("qlk_management.action_bd_dashboard", raise_if_not_found=False)
        return self.env.ref("qlk_management.action_project_dashboard", raise_if_not_found=False)

    # ------------------------------------------------------------------------------
    # هذه الدالة تبني رابط إعادة التوجيه إلى داشبورد المستخدم بعد تسجيل الدخول.
    # ------------------------------------------------------------------------------
    def get_dashboard_redirect_url(self):
        self.ensure_one()
        action = self._qlk_preferred_dashboard_action()
        if action:
            return f"/web#action={action.id}"
        return "/web"

    # ------------------------------------------------------------------------------
    # هذه الدالة تُسند مجموعة صلاحيات العملاء للمستخدمين المطلوبين بالاسم/الدخول.
    # ------------------------------------------------------------------------------
    @api.model
    def _assign_default_client_access_group(self):
        group = self.env.ref("qlk_management.group_client_data_access", raise_if_not_found=False)
        if not group:
            return False

        target_names = ["MP", "BD", "Mr. Abdulla", "Mr. Mansoor"]
        target_logins = ["mp", "bd", "abdulla", "mansoor"]
        users = self.search([
            "|",
            ("name", "in", target_names),
            ("login", "in", target_logins),
        ])
        if users:
            users.write({"groups_id": [(4, group.id)]})
        return True

    def notify_warning(self, message, title=None, sticky=False):
        """Send a warning notification to the current user's bus channel when available."""
        if not message:
            return
        payload = {
            "message": message,
            "type": "warning",
            "sticky": bool(sticky),
        }
        if title:
            payload["title"] = title
        if "bus.bus" in self.env:
            for user in self:
                if user.partner_id:
                    self.env["bus.bus"]._sendone(user.partner_id, "display_notification", payload)
            return
        # Fallback: log on partner record when bus is not available.
        for user in self:
            if user.partner_id:
                user.partner_id.message_post(body=message, subject=title or _("Warning"))
