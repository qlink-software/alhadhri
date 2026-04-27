# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.fields import Command


class ResUsers(models.Model):
    _inherit = "res.users"

    qlk_access_group_ids = fields.Many2many(
        "res.groups",
        string="Operational Access Groups",
        compute="_compute_qlk_access_group_ids",
        help="Shows the existing operational groups used by QLink access control.",
    )

    @api.depends("groups_id")
    def _compute_qlk_access_group_ids(self):
        group_xmlids = [
            "qlk_management.group_bd_user",
            "qlk_management.group_bd_manager",
            "qlk_management.group_el_user",
            "qlk_management.group_el_manager",
            "qlk_management.group_pre_litigation_user",
            "qlk_management.group_pre_litigation_manager",
            "qlk_task_management.group_task_user",
            "qlk_task_management.group_task_manager",
            "qlk_management.group_hr_user",
            "qlk_management.group_hr_manager",
            "qlk_law.group_qlk_law_lawyer",
            "qlk_law.group_qlk_law_manager",
            "qlk_corporate.group_corporate_user",
            "qlk_corporate.group_corporate_manager",
            "qlk_arbitration.group_arbitration_user",
            "qlk_arbitration.group_arbitration_manager",
            "base.group_system",
        ]
        access_groups = self.env["res.groups"]
        for xmlid in group_xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                access_groups |= group
        for user in self:
            user.qlk_access_group_ids = [Command.set((user.groups_id & access_groups).ids)]

    # ------------------------------------------------------------------------------
    # هذه الدالة تحدد هل المستخدم يمتلك صلاحية عرض جميع بيانات الداشبورد
    # (مثل MP أو مدير BD) أم يجب أن يرى بياناته الشخصية فقط.
    # ------------------------------------------------------------------------------
    def _qlk_can_view_all_dashboards(self):
        self.ensure_one()
        return (
            self.has_group("base.group_system")
            or self.has_group("qlk_management.group_pre_litigation_manager")
            or self.has_group("qlk_management.group_bd_manager")
            or self.has_group("qlk_management.group_el_manager")
            or self.has_group("qlk_task_management.group_task_manager")
            or self.has_group("qlk_management.group_hr_manager")
            or self.has_group("qlk_corporate.group_corporate_manager")
            or self.has_group("qlk_arbitration.group_arbitration_manager")
        )

    # ------------------------------------------------------------------------------
    # هذه الدالة تحدد أكشن الداشبورد الافتراضي للمستخدم بعد تسجيل الدخول.
    # ------------------------------------------------------------------------------
    def _qlk_preferred_dashboard_action(self):
        self.ensure_one()
        if self.has_group("qlk_management.group_bd_manager"):
            return self.env.ref("qlk_management.action_bd_dashboard", raise_if_not_found=False)
        return self.env.ref("qlk_management.action_analysis_dashboard", raise_if_not_found=False)

    # ------------------------------------------------------------------------------
    # هذه الدالة تبني رابط إعادة التوجيه إلى داشبورد المستخدم بعد تسجيل الدخول.
    # ------------------------------------------------------------------------------
    def get_dashboard_redirect_url(self):
        self.ensure_one()
        action = self._qlk_preferred_dashboard_action()
        if action:
            return f"/web#action={action.id}"
        return "/web"

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
