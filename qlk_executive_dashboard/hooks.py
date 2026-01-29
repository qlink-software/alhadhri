# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def post_init_hook(env_or_cr, registry=None):
    if registry is None and hasattr(env_or_cr, "cr"):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    action = env.ref("qlk_executive_dashboard.action_qlk_executive_dashboard", raise_if_not_found=False)
    if not action:
        return
    users_model = env["res.users"]
    if "action_id" in users_model._fields:
        field_name = "action_id"
    elif "home_action_id" in users_model._fields:
        field_name = "home_action_id"
    else:
        return

    group_manager = env.ref("qlk_executive_dashboard.group_qlk_manager", raise_if_not_found=False)
    group_assistant = env.ref("qlk_executive_dashboard.group_qlk_assistant_manager", raise_if_not_found=False)
    group_ids = [group.id for group in (group_manager, group_assistant) if group]
    if not group_ids:
        return

    users = users_model.search([
        ("groups_id", "in", group_ids),
        (field_name, "=", False),
    ])
    if users:
        users.write({field_name: action.id})
