# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.fields import Command


class ResUsers(models.Model):
    _inherit = "res.users"

    department_role_ids = fields.One2many(
        "qlk.user.department.role",
        "user_id",
        string="Department Roles",
    )
    department_ids = fields.Many2many(
        "qlk.department",
        "qlk_user_department_rel",
        "user_id",
        "department_id",
        string="Departments",
        compute="_compute_department_access",
        store=True,
    )
    manager_department_ids = fields.Many2many(
        "qlk.department",
        "qlk_user_manager_department_rel",
        "user_id",
        "department_id",
        string="Managed Departments",
        compute="_compute_department_access",
        store=True,
    )
    user_department_ids = fields.Many2many(
        "qlk.department",
        "qlk_user_member_department_rel",
        "user_id",
        "department_id",
        string="User Departments",
        compute="_compute_department_access",
        store=True,
    )
    qlk_access_group_ids = fields.Many2many(
        "res.groups",
        string="Operational Access Groups",
        compute="_compute_qlk_access_group_ids",
        help="Shows the existing operational groups used by QLink access control.",
    )

    @api.depends("department_role_ids.department_id", "department_role_ids.role_type")
    def _compute_department_access(self):
        for user in self:
            roles = user.department_role_ids
            departments = roles.mapped("department_id")
            manager_departments = roles.filtered(lambda role: role.role_type == "manager").mapped("department_id")
            user_departments = roles.filtered(lambda role: role.role_type == "user").mapped("department_id")
            user.department_ids = [Command.set(departments.ids)]
            user.manager_department_ids = [Command.set(manager_departments.ids)]
            user.user_department_ids = [Command.set(user_departments.ids)]

    @api.depends("groups_id")
    def _compute_qlk_access_group_ids(self):
        group_xmlids = [
            "qlk_management.bd_manager_group",
            "qlk_management.bd_assistant_manager_group",
            "qlk_management.group_legal_user",
            "qlk_management.group_legal_manager",
            "qlk_law.group_qlk_law_lawyer",
            "qlk_law.group_qlk_law_manager",
            "qlk_corporate.group_corporate_user",
            "qlk_corporate.group_corporate_responsible",
            "qlk_corporate.group_corporate_manager",
            "qlk_arbitration.group_arbitration_user",
            "qlk_arbitration.group_arbitration_responsible",
            "qlk_arbitration.group_arbitration_manager",
            "qlk_management.group_mp",
            "qlk_management.group_qlk_admin",
        ]
        access_groups = self.env["res.groups"]
        for xmlid in group_xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                access_groups |= group
        for user in self:
            user.qlk_access_group_ids = [Command.set((user.groups_id & access_groups).ids)]

    def write(self, vals):
        result = super().write(vals)
        if "department_role_ids" in vals and not self.env.context.get("skip_department_group_sync"):
            self.env["qlk.user.department.role"]._sync_user_groups(self)
        return result

    # ------------------------------------------------------------------------------
    # هذه الدالة تحدد هل المستخدم يمتلك صلاحية عرض جميع بيانات الداشبورد
    # (مثل MP أو مدير BD) أم يجب أن يرى بياناته الشخصية فقط.
    # ------------------------------------------------------------------------------
    def _qlk_can_view_all_dashboards(self):
        self.ensure_one()
        return bool(self.manager_department_ids)

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
        full_access_group = self.env.ref("qlk_management.group_client_data_access", raise_if_not_found=False)
        mp_group = self.env.ref("qlk_management.group_client_mp", raise_if_not_found=False)
        bd_group = self.env.ref("qlk_management.group_client_bd", raise_if_not_found=False)
        view_group = self.env.ref("qlk_management.group_client_view_only", raise_if_not_found=False)
        if not full_access_group or not mp_group or not bd_group or not view_group:
            return False

        internal_users = self.search([("share", "=", False), ("groups_id", "in", self.env.ref("base.group_user").id)])
        mp_users = internal_users.filtered(lambda user: user.has_group("qlk_management.group_mp"))
        bd_users = internal_users.filtered(
            lambda user: user.has_group("qlk_management.bd_manager_group")
            or user.has_group("qlk_management.bd_assistant_manager_group")
        )
        privileged_users = mp_users | bd_users
        view_only_users = internal_users - privileged_users

        if mp_users:
            mp_users.write({"groups_id": [(4, mp_group.id), (4, full_access_group.id), (3, view_group.id)]})
        if bd_users:
            bd_users.write({"groups_id": [(4, bd_group.id), (4, full_access_group.id), (3, view_group.id)]})
        if view_only_users:
            view_only_users.write({"groups_id": [(4, view_group.id)]})
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
