# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.fields import Command
from odoo.exceptions import ValidationError


class QlkDepartment(models.Model):
    _name = "qlk.department"
    _description = "QLink Legal Department"
    _order = "sequence, name"

    name = fields.Char(string="Department", required=True, translate=True)
    code = fields.Char(string="Code", required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    user_group_id = fields.Many2one(
        "res.groups",
        string="User Menu Group",
        readonly=True,
        copy=False,
        help="Technical group used only for menu visibility.",
    )
    manager_group_id = fields.Many2one(
        "res.groups",
        string="Manager Menu Group",
        readonly=True,
        copy=False,
        help="Technical group used only for menu visibility.",
    )

    _sql_constraints = [
        ("qlk_department_code_unique", "unique(code)", "Department code must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_department_groups()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"name", "code", "user_group_id", "manager_group_id"} & set(vals):
            self._ensure_department_groups()
            self.env["qlk.user.department.role"]._sync_user_groups()
        return result

    def _ensure_department_groups(self):
        """Create menu groups for dynamic departments without exposing them as the admin UI."""
        category = self.env.ref("qlk_management.module_qlk_department_access", raise_if_not_found=False)
        if not category:
            category = self.env["ir.module.category"].sudo().create(
                {"name": "QLink Department Access", "sequence": 35}
            )
        for department in self.sudo():
            updates = {}
            if not department.user_group_id:
                updates["user_group_id"] = self.env["res.groups"].sudo().create(
                    {
                        "name": _("Department %(name)s User", name=department.name),
                        "category_id": category.id,
                        "implied_ids": [Command.link(self.env.ref("base.group_user").id)],
                    }
                ).id
            if not department.manager_group_id:
                implied_ids = [Command.link(self.env.ref("base.group_user").id)]
                if updates.get("user_group_id"):
                    implied_ids.append(Command.link(updates["user_group_id"]))
                elif department.user_group_id:
                    implied_ids.append(Command.link(department.user_group_id.id))
                updates["manager_group_id"] = self.env["res.groups"].sudo().create(
                    {
                        "name": _("Department %(name)s Manager", name=department.name),
                        "category_id": category.id,
                        "implied_ids": implied_ids,
                    }
                ).id
            if updates:
                department.with_context(skip_department_group_sync=True).write(updates)

    @api.model
    def _get_by_code(self, code):
        if not code:
            return self.browse()
        return self.search([("code", "=", code)], limit=1)

    @api.model
    def _get_by_codes(self, codes):
        codes = [code for code in codes if code]
        departments = self.search([("code", "in", list(set(codes)))]) if codes else self.browse()
        return {department.code: department for department in departments}

    @api.model
    def _sync_access_control_after_data(self):
        """Backfill security helper fields after department data is loaded on upgrade."""
        self.search([])._ensure_department_groups()
        self._bootstrap_roles_from_legacy_groups()
        self.env["qlk.user.department.role"]._sync_user_groups()
        secured_models = [
            "qlk.project",
            "qlk.case",
            "qlk.task",
            "project.task",
            "task",
            "crm.lead",
            "bd.proposal",
            "bd.engagement.letter",
            "project.project",
            "qlk.corporate.case",
            "qlk.arbitration.case",
        ]
        for model_name in secured_models:
            Model = self.env.get(model_name)
            if not Model or not hasattr(Model, "_compute_department_security_fields"):
                continue
            records = Model.sudo().with_context(active_test=False).search([])
            for index in range(0, len(records), 500):
                records[index : index + 500]._compute_department_security_fields()
        return True

    @api.model
    def _bootstrap_roles_from_legacy_groups(self):
        """Create initial friendly roles from older static groups without overwriting admin choices."""
        Role = self.env["qlk.user.department.role"].sudo()
        departments = self.sudo()._get_by_codes(["litigation", "corporate", "arbitration", "mp"])
        mappings = [
            ("qlk_management.group_qlk_managers", ["litigation", "corporate", "arbitration", "mp"], "manager"),
            ("qlk_management.bd_manager_group", ["litigation", "corporate", "arbitration"], "manager"),
            ("qlk_management.group_mp", ["mp"], "manager"),
            ("qlk_management.group_qlk_lawyers", ["litigation"], "user"),
            ("qlk_management.group_legal_user", ["litigation"], "user"),
            ("qlk_management.group_legal_manager", ["litigation"], "manager"),
            ("qlk_corporate.group_corporate_user", ["corporate"], "user"),
            ("qlk_corporate.group_corporate_responsible", ["corporate"], "user"),
            ("qlk_corporate.group_corporate_manager", ["corporate"], "manager"),
            ("qlk_arbitration.group_arbitration_user", ["arbitration"], "user"),
            ("qlk_arbitration.group_arbitration_responsible", ["arbitration"], "user"),
            ("qlk_arbitration.group_arbitration_manager", ["arbitration"], "manager"),
        ]
        for group_xmlid, department_codes, role_type in mappings:
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if not group:
                continue
            for user in group.sudo().users.filtered(lambda item: not item.share):
                for code in department_codes:
                    department = departments.get(code)
                    if not department:
                        continue
                    existing = Role.search(
                        [("user_id", "=", user.id), ("department_id", "=", department.id)],
                        limit=1,
                    )
                    if existing:
                        if role_type == "manager" and existing.role_type != "manager":
                            existing.role_type = "manager"
                        continue
                    Role.create(
                        {
                            "user_id": user.id,
                            "department_id": department.id,
                            "role_type": role_type,
                        }
                    )
        return True


class QlkUserDepartmentRole(models.Model):
    _name = "qlk.user.department.role"
    _description = "User Department Role"
    _order = "user_id, department_id"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        ondelete="cascade",
        index=True,
    )
    department_id = fields.Many2one(
        "qlk.department",
        string="Department",
        required=True,
        ondelete="cascade",
        index=True,
    )
    role_type = fields.Selection(
        selection=[
            ("manager", "Manager"),
            ("user", "User"),
        ],
        string="Role",
        required=True,
        default="user",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="user_id.company_id",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "qlk_user_department_role_unique",
            "unique(user_id, department_id)",
            "The user already has a role in this department.",
        ),
    ]

    @api.constrains("department_id", "role_type")
    def _check_department_groups(self):
        for role in self:
            if not role.department_id.user_group_id or not role.department_id.manager_group_id:
                role.department_id._ensure_department_groups()

    @api.model_create_multi
    def create(self, vals_list):
        roles = super().create(vals_list)
        roles.department_id._ensure_department_groups()
        self._sync_user_groups(roles.user_id)
        return roles

    def write(self, vals):
        users = self.user_id
        result = super().write(vals)
        users |= self.user_id
        if {"user_id", "department_id", "role_type"} & set(vals):
            self.department_id._ensure_department_groups()
            self._sync_user_groups(users)
        return result

    def unlink(self):
        users = self.user_id
        result = super().unlink()
        self._sync_user_groups(users)
        return result

    @api.model
    def _sync_user_groups(self, users=None):
        """Synchronize friendly department-role rows into menu groups."""
        Department = self.env["qlk.department"].sudo()
        departments = Department.search([])
        managed_group_ids = set((departments.mapped("user_group_id") | departments.mapped("manager_group_id")).ids)
        if not managed_group_ids:
            return True

        users = users.sudo() if users else self.env["res.users"].sudo().search([("share", "=", False)])
        roles_by_user = {user.id: self.browse() for user in users}
        roles = self.sudo().search([("user_id", "in", users.ids)])
        for role in roles:
            roles_by_user.setdefault(role.user_id.id, self.browse())
            roles_by_user[role.user_id.id] |= role

        for user in users:
            commands = [Command.unlink(group_id) for group_id in managed_group_ids if group_id in user.groups_id.ids]
            for role in roles_by_user.get(user.id, self.browse()):
                department = role.department_id
                if department.user_group_id:
                    commands.append(Command.link(department.user_group_id.id))
                if role.role_type == "manager" and department.manager_group_id:
                    commands.append(Command.link(department.manager_group_id.id))
            if commands:
                user.with_context(skip_department_group_sync=True).write({"groups_id": commands})
        return True

    @api.constrains("role_type")
    def _check_role_type(self):
        for role in self:
            if role.role_type not in {"manager", "user"}:
                raise ValidationError(_("Invalid department role."))
