# -*- coding: utf-8 -*-

from odoo import api, models


class IrRule(models.Model):
    _inherit = "ir.rule"

    @api.model
    def _qlk_disable_legacy_rules(self):
        xmlids = (
            "qlk_management.rule_qlk_case_manager_all",
            "qlk_task_management.rule_qlk_task_all_users",
            "qlk_management.rule_project_task_manager_all",
            "qlk_management.rule_management_task_manager_all",
            "qlk_management.rule_crm_lead_bd_access",
            "qlk_management.rule_crm_lead_default_deny",
            "project.project_project_manager_rule",
            "project.project_public_members_rule",
            "project.task_visibility_rule",
            "project.project_manager_all_project_tasks_rule",
            "project.task_visibility_rule_project_user",
            "project.ir_rule_private_task",
            "crm.crm_rule_personal_lead",
            "crm.crm_rule_all_lead",
        )
        rules = self.browse()
        for xmlid in xmlids:
            rule = self.env.ref(xmlid, raise_if_not_found=False)
            if rule and rule._name == "ir.rule":
                rules |= rule
        if rules:
            rules.write({"active": False})
