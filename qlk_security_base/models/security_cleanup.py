# -*- coding: utf-8 -*-
from odoo import api, models


class QlkSecurityCleanup(models.AbstractModel):
    _name = "qlk.security.cleanup"
    _description = "QLK Security Cleanup"

    LEGACY_GROUP_XMLIDS = (
        "hr_recruitment_automation.group_hr_user",
        "hr_recruitment_automation.group_hr_manager",
        "qlk_management.group_task_user",
        "qlk_management.group_task_manager",
        "qlk_management.group_client_data_access",
        "qlk_management.group_client_mp",
        "qlk_management.group_client_bd",
        "qlk_management.group_client_view_only",
    )

    @api.model
    def cleanup_legacy_security_groups(self):
        hidden_category = self.env.ref("base.module_category_hidden", raise_if_not_found=False)
        legacy_group_ids = []
        for xmlid in self.LEGACY_GROUP_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                legacy_group_ids.append(group.id)
                values = {"name": f"Deprecated {xmlid}"}
                if hidden_category:
                    values["category_id"] = hidden_category.id
                group.sudo().write(values)
        if legacy_group_ids:
            self.env.cr.execute("DELETE FROM ir_model_access WHERE group_id = ANY(%s)", (legacy_group_ids,))
            self.env.cr.execute("DELETE FROM rule_group_rel WHERE group_id = ANY(%s)", (legacy_group_ids,))
            self.env.cr.execute("DELETE FROM res_groups_users_rel WHERE gid = ANY(%s)", (legacy_group_ids,))
            self.env.cr.execute("DELETE FROM res_groups_implied_rel WHERE gid = ANY(%s) OR hid = ANY(%s)", (legacy_group_ids, legacy_group_ids))
        return True
