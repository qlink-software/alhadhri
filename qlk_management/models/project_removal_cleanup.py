# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.tools.sql import column_exists, table_exists


class QlkProjectRemovalCleanup(models.AbstractModel):
    _name = "qlk.project.removal.cleanup"
    _description = "QLK Project Removal Cleanup"

    OBSOLETE_MODELS = (
        "qlk.project.fee",
        "qlk.project.stage",
        "qlk.project.stage.line",
        "qlk.project.dashboard",
        "qlk.project.log.hours",
        "qlk.project.transfer.arbitration",
        "qlk.project.transfer.corporate",
        "qlk.project.transfer.litigation",
        "qlk.project.create.litigation.case",
        "qlk.user.department.role",
        "qlk.department",
    )

    OBSOLETE_XMLIDS = (
        "qlk_management.action_project_dashboard",
        "qlk_management.action_qlk_project_tasks",
        "qlk_management.action_qlk_project_hours",
        "qlk_management.action_qlk_project_stage",
        "qlk_management.action_qlk_project_litigation",
        "qlk_management.action_qlk_project_corporate",
        "qlk_management.action_qlk_project_arbitration",
        "qlk_management.group_qlk_project_user",
        "qlk_management.group_qlk_project_manager",
        "qlk_management.group_qlk_project_stage_user",
        "qlk_management.group_qlk_project_stage_manager",
        "qlk_management.menu_qlk_project_projects",
        "qlk_management.menu_qlk_project_projects_list",
        "qlk_management.menu_qlk_project_working_hours",
        "qlk_management.menu_qlk_project_tasks",
        "qlk_management.menu_qlk_project_hours",
        "qlk_management.menu_qlk_project_stages",
        "qlk_management.menu_qlk_project_dashboards_root",
        "qlk_management.menu_project_dashboard_entry",
        "qlk_management.menu_qlk_project_analytics_dashboard",
        "qlk_management.rule_qlk_project_user",
        "qlk_management.rule_qlk_project_manager",
        "qlk_management.rule_qlk_project_stage_user",
        "qlk_management.rule_qlk_project_stage_manager",
        "qlk_management.seq_qlk_project",
        "qlk_management.mail_template_project_mp_assignment",
        "qlk_management.view_qlk_project_stage_list",
        "qlk_management.view_qlk_project_stage_form",
        "qlk_management.view_qlk_project_stage_search",
        "qlk_management.view_project_dashboard_action",
        "qlk_management.view_project_log_hours_form",
        "qlk_management.view_project_transfer_litigation_form",
        "qlk_management.view_project_create_litigation_case_form",
        "qlk_management.view_project_transfer_corporate_form",
        "qlk_management.view_project_transfer_arbitration_form",
        "qlk_management.module_qlk_department_access",
        "qlk_management.department_litigation",
        "qlk_management.department_corporate",
        "qlk_management.department_arbitration",
        "qlk_management.department_mp",
        "qlk_management.group_qlk_department_user",
        "qlk_management.group_qlk_department_manager",
        "qlk_management.access_qlk_department_internal",
        "qlk_management.access_qlk_department_user",
        "qlk_management.access_qlk_department_admin",
        "qlk_management.access_qlk_department_qlk_admin",
        "qlk_management.rule_qlk_department_user",
        "qlk_management.rule_qlk_department_manager",
        "qlk_management.view_qlk_department_list",
        "qlk_management.view_qlk_department_form",
        "qlk_management.action_qlk_department",
        "qlk_management.menu_qlk_department_access",
        "qlk_management.view_users_form_department_access",
    )

    REMOVED_COLUMNS = {
        "bd_engagement_letter": ("qlk_project_id", "allow_project_without_payment", "can_create_project", "department_id"),
        "qlk_case": ("project_sequence", "project_litigation_level_ids", "department_id"),
        "qlk_task": ("department_id",),
        "qlk_pre_litigation": (),
        "qlk_corporate_case": ("department_id",),
        "qlk_arbitration_case": ("department_id",),
        "qlk_internal_request": ("project_id",),
        "res_users": ("department_role_ids",),
        "project_task": ("department_id",),
        "task": ("department_id",),
        "crm_lead": ("department_id",),
        "bd_proposal": ("department_id",),
        "project_project": ("department_id",),
    }
    REMOVED_FIELD_METADATA = {
        "bd.engagement.letter": ("qlk_project_id", "allow_project_without_payment", "can_create_project", "department_id"),
        "qlk.case": ("project_sequence", "project_litigation_level_ids", "department_id"),
        "qlk.task": ("department_id",),
        "qlk.pre.litigation": (),
        "qlk.corporate.case": ("department_id",),
        "qlk.arbitration.case": ("department_id",),
        "qlk.internal.request": ("project_id",),
        "res.users": ("department_role_ids", "department_ids", "manager_department_ids", "user_department_ids"),
        "project.task": ("department_id",),
        "task": ("department_id",),
        "crm.lead": ("department_id",),
        "bd.proposal": ("department_id",),
        "project.project": ("department_id",),
    }

    OBSOLETE_TABLES = (
        "qlk_project_fee",
        "qlk_project_stage",
        "qlk_project_stage_line",
        "qlk_project_log_hours",
        "qlk_project_transfer_arbitration",
        "qlk_project_transfer_corporate",
        "qlk_project_transfer_litigation",
        "qlk_project_create_litigation_case",
        "qlk_user_department_role",
        "qlk_project_translation_attachment_rel",
        "qlk_project_lawyer_rel",
        "qlk_project_litigation_level_rel",
        "qlk_project_employee_rel",
        "qlk_project_poa_rel",
        "qlk_project_access_lawyer_rel",
        "qlk_project_stage_line_attachment_rel",
        "qlk_department",
        "qlk_user_department_rel",
        "qlk_user_manager_department_rel",
        "qlk_user_member_department_rel",
    )

    @api.model
    def cleanup_removed_project_models(self):
        self._remove_stale_user_role_views()
        self._remove_obsolete_menus_and_actions()
        self._sanitize_broken_menu_actions()
        self._unlink_obsolete_xml_records()
        self._drop_removed_columns()
        self._drop_obsolete_tables()
        self._remove_model_metadata()
        self._refresh_user_groups_view()
        return True

    def _remove_stale_user_role_views(self):
        cr = self.env.cr
        cr.execute(
            """
            SELECT id
              FROM ir_ui_view
             WHERE model = 'res.users'
               AND (
                    arch_db::text LIKE '%%department_role_ids%%'
                 OR arch_db::text LIKE '%%department_ids%%'
                 OR arch_db::text LIKE '%%manager_department_ids%%'
                 OR arch_db::text LIKE '%%user_department_ids%%'
               )
            """
        )
        view_ids = [row[0] for row in cr.fetchall()]
        if not view_ids:
            return
        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE model = 'ir.ui.view'
               AND res_id = ANY(%s)
            """,
            (view_ids,),
        )
        cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (view_ids,))

    def _refresh_user_groups_view(self):
        groups_model = self.env["res.groups"].sudo()
        update_user_groups_view = getattr(groups_model, "_update_user_groups_view", None)
        if callable(update_user_groups_view):
            update_user_groups_view()

    def _remove_obsolete_menus_and_actions(self):
        cr = self.env.cr
        obsolete_xml_names = [xmlid.split(".", 1)[1] for xmlid in self.OBSOLETE_XMLIDS]
        cr.execute(
            """
            SELECT res_id
              FROM ir_model_data
             WHERE module = 'qlk_management'
               AND model = 'ir.ui.menu'
               AND name = ANY(%s)
            """,
            (obsolete_xml_names,),
        )
        menu_ids = [row[0] for row in cr.fetchall()]

        cr.execute(
            """
            SELECT id, 'ir.actions.act_window'
              FROM ir_act_window
             WHERE res_model = ANY(%s)
            UNION ALL
            SELECT id, 'ir.actions.client'
              FROM ir_act_client
             WHERE tag = 'qlk.project.dashboard'
                OR res_model = ANY(%s)
            """,
            (list(self.OBSOLETE_MODELS), list(self.OBSOLETE_MODELS)),
        )
        action_refs = ["%s,%s" % (model, action_id) for action_id, model in cr.fetchall()]
        if action_refs:
            cr.execute("SELECT id FROM ir_ui_menu WHERE action = ANY(%s)", (action_refs,))
            menu_ids.extend(row[0] for row in cr.fetchall())

        if menu_ids:
            cr.execute(
                """
                WITH RECURSIVE doomed(id) AS (
                    SELECT id FROM ir_ui_menu WHERE id = ANY(%s)
                    UNION
                    SELECT child.id
                      FROM ir_ui_menu child
                      JOIN doomed parent ON child.parent_id = parent.id
                )
                DELETE FROM ir_ui_menu_group_rel
                 WHERE menu_id IN (SELECT id FROM doomed)
                """,
                (menu_ids,),
            )
            cr.execute(
                """
                WITH RECURSIVE doomed(id) AS (
                    SELECT id FROM ir_ui_menu WHERE id = ANY(%s)
                    UNION
                    SELECT child.id
                      FROM ir_ui_menu child
                      JOIN doomed parent ON child.parent_id = parent.id
                )
                DELETE FROM ir_model_data
                 WHERE model = 'ir.ui.menu'
                   AND res_id IN (SELECT id FROM doomed)
                """,
                (menu_ids,),
            )
            cr.execute(
                """
                WITH RECURSIVE doomed(id) AS (
                    SELECT id FROM ir_ui_menu WHERE id = ANY(%s)
                    UNION
                    SELECT child.id
                      FROM ir_ui_menu child
                      JOIN doomed parent ON child.parent_id = parent.id
                )
                DELETE FROM ir_ui_menu
                 WHERE id IN (SELECT id FROM doomed)
                """,
                (menu_ids,),
            )

        cr.execute(
            """
            UPDATE ir_ui_menu AS menu
               SET action = NULL
             WHERE action LIKE 'ir.actions.act_window,%%'
               AND NOT EXISTS (
                   SELECT 1
                     FROM ir_act_window action
                    WHERE action.id = split_part(menu.action, ',', 2)::integer
               )
            """
        )
        cr.execute(
            """
            UPDATE ir_ui_menu AS menu
               SET action = NULL
             WHERE action LIKE 'ir.actions.client,%%'
               AND NOT EXISTS (
                   SELECT 1
                     FROM ir_act_client action
                    WHERE action.id = split_part(menu.action, ',', 2)::integer
               )
            """
        )
        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE module = 'qlk_management'
               AND model IN ('ir.actions.act_window', 'ir.actions.client')
               AND name = ANY(%s)
            """,
            (obsolete_xml_names,),
        )
        cr.execute("DELETE FROM ir_act_window WHERE res_model = ANY(%s)", (list(self.OBSOLETE_MODELS),))
        cr.execute(
            """
            DELETE FROM ir_act_client
             WHERE tag = 'qlk.project.dashboard'
                OR res_model = ANY(%s)
            """,
            (list(self.OBSOLETE_MODELS),),
        )

    def _sanitize_broken_menu_actions(self):
        cr = self.env.cr
        updated = 0
        queries = (
            (
                """
                UPDATE ir_ui_menu AS menu
                   SET action = NULL
                 WHERE action ~ '^ir\\.actions\\.act_window,[0-9]+$'
                   AND NOT EXISTS (
                       SELECT 1
                         FROM ir_act_window action
                        WHERE action.id = split_part(menu.action, ',', 2)::integer
                   )
                """
            ),
            (
                """
                UPDATE ir_ui_menu AS menu
                   SET action = NULL
                 WHERE action ~ '^ir\\.actions\\.client,[0-9]+$'
                   AND NOT EXISTS (
                       SELECT 1
                         FROM ir_act_client action
                        WHERE action.id = split_part(menu.action, ',', 2)::integer
                   )
                """
            ),
            (
                """
                UPDATE ir_ui_menu AS menu
                   SET action = NULL
                 WHERE action ~ '^ir\\.actions\\.server,[0-9]+$'
                   AND NOT EXISTS (
                       SELECT 1
                         FROM ir_act_server action
                        WHERE action.id = split_part(menu.action, ',', 2)::integer
                   )
                """
            ),
            (
                """
                UPDATE ir_ui_menu AS menu
                   SET action = NULL
                 WHERE action ~ '^ir\\.actions\\.report,[0-9]+$'
                   AND NOT EXISTS (
                       SELECT 1
                         FROM ir_act_report_xml action
                        WHERE action.id = split_part(menu.action, ',', 2)::integer
                   )
                """
            ),
            (
                """
                UPDATE ir_ui_menu AS menu
                   SET action = NULL
                 WHERE action ~ '^ir\\.actions\\.act_url,[0-9]+$'
                   AND NOT EXISTS (
                       SELECT 1
                         FROM ir_act_url action
                        WHERE action.id = split_part(menu.action, ',', 2)::integer
                   )
                """
            ),
            (
                """
                UPDATE ir_ui_menu
                   SET action = NULL
                 WHERE action IS NOT NULL
                   AND action !~ '^ir\\.actions\\.(act_window|client|server|report|act_url),[0-9]+$'
                """
            ),
        )
        for query in queries:
            cr.execute(query)
            updated += cr.rowcount

        cr.execute("SELECT id, res_model FROM ir_act_window WHERE res_model IS NOT NULL")
        invalid_window_action_ids = [
            action_id for action_id, model_name in cr.fetchall() if model_name not in self.env
        ]
        if invalid_window_action_ids:
            cr.execute(
                """
                UPDATE ir_ui_menu
                   SET action = NULL
                 WHERE action = ANY(%s)
                """,
                (["ir.actions.act_window,%s" % action_id for action_id in invalid_window_action_ids],),
            )
            updated += cr.rowcount

        cr.execute("SELECT id, model_name FROM ir_act_server WHERE model_name IS NOT NULL")
        invalid_server_action_ids = [
            action_id for action_id, model_name in cr.fetchall() if model_name not in self.env
        ]
        if invalid_server_action_ids:
            cr.execute(
                """
                UPDATE ir_ui_menu
                   SET action = NULL
                 WHERE action = ANY(%s)
                """,
                (["ir.actions.server,%s" % action_id for action_id in invalid_server_action_ids],),
            )
            updated += cr.rowcount

        cr.execute("SELECT id, model FROM ir_act_report_xml WHERE model IS NOT NULL")
        invalid_report_action_ids = [
            action_id for action_id, model_name in cr.fetchall() if model_name not in self.env
        ]
        if invalid_report_action_ids:
            cr.execute(
                """
                UPDATE ir_ui_menu
                   SET action = NULL
                 WHERE action = ANY(%s)
                """,
                (["ir.actions.report,%s" % action_id for action_id in invalid_report_action_ids],),
            )
            updated += cr.rowcount

        if updated:
            self.env.registry.clear_cache()
        return updated

    def _unlink_obsolete_xml_records(self):
        cr = self.env.cr
        imd_model = self.env["ir.model.data"].sudo()
        for xmlid in self.OBSOLETE_XMLIDS:
            module, name = xmlid.split(".", 1)
            imd_records = imd_model.search([("module", "=", module), ("name", "=", name)])
            for imd in imd_records:
                if imd.model == "res.groups":
                    cr.execute("DELETE FROM res_groups_users_rel WHERE gid = %s", (imd.res_id,))
                    cr.execute(
                        "DELETE FROM res_groups_implied_rel WHERE gid = %s OR hid = %s",
                        (imd.res_id, imd.res_id),
                    )
                    cr.execute("DELETE FROM ir_ui_menu_group_rel WHERE gid = %s", (imd.res_id,))
                    if table_exists(cr, "rule_group_rel"):
                        cr.execute("DELETE FROM rule_group_rel WHERE group_id = %s", (imd.res_id,))
                    cr.execute("UPDATE ir_model_access SET group_id = NULL WHERE group_id = %s", (imd.res_id,))
                if imd.model in self.env:
                    record = self.env[imd.model].browse(imd.res_id).exists()
                    if record:
                        record.sudo().unlink()
                imd.unlink()

    def _drop_removed_columns(self):
        cr = self.env.cr
        for table, columns in self.REMOVED_COLUMNS.items():
            if not table_exists(cr, table):
                continue
            for column in columns:
                if column_exists(cr, table, column):
                    cr.execute(
                        'ALTER TABLE "%s" DROP COLUMN "%s" CASCADE'
                        % (table.replace('"', '""'), column.replace('"', '""'))
                    )

    def _drop_obsolete_tables(self):
        cr = self.env.cr
        for table in self.OBSOLETE_TABLES:
            if table_exists(cr, table):
                cr.execute('DROP TABLE "%s" CASCADE' % table.replace('"', '""'))

    def _remove_model_metadata(self):
        cr = self.env.cr
        cr.execute(
            "DELETE FROM ir_model_access WHERE model_id IN (SELECT id FROM ir_model WHERE model = ANY(%s))",
            (list(self.OBSOLETE_MODELS),),
        )
        cr.execute(
            "DELETE FROM ir_rule WHERE model_id IN (SELECT id FROM ir_model WHERE model = ANY(%s))",
            (list(self.OBSOLETE_MODELS),),
        )
        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE model = 'ir.model.constraint'
               AND res_id IN (
                   SELECT id
                     FROM ir_model_constraint
                    WHERE model IN (SELECT id FROM ir_model WHERE model = ANY(%s))
                       OR name = ANY(%s)
               )
            """,
            (
                list(self.OBSOLETE_MODELS),
                [
                    "task_department_id_fkey",
                    "crm_lead_department_id_fkey",
                    "project_project_department_id_fkey",
                    "project_task_department_id_fkey",
                    "bd_proposal_department_id_fkey",
                    "bd_engagement_letter_department_id_fkey",
                    "qlk_task_department_id_fkey",
                    "qlk_user_department_rel_user_id_fkey",
                    "qlk_user_department_rel_department_id_fkey",
                    "qlk_user_manager_department_rel_user_id_fkey",
                    "qlk_user_manager_department_rel_department_id_fkey",
                    "qlk_user_member_department_rel_user_id_fkey",
                    "qlk_user_member_department_rel_department_id_fkey",
                    "qlk_arbitration_case_department_id_fkey",
                    "qlk_case_department_id_fkey",
                    "qlk_corporate_case_department_id_fkey",
                ],
            ),
        )
        cr.execute(
            """
            DELETE FROM ir_model_constraint
             WHERE model IN (SELECT id FROM ir_model WHERE model = ANY(%s))
                OR name = ANY(%s)
            """,
            (
                list(self.OBSOLETE_MODELS),
                [
                    "task_department_id_fkey",
                    "crm_lead_department_id_fkey",
                    "project_project_department_id_fkey",
                    "project_task_department_id_fkey",
                    "bd_proposal_department_id_fkey",
                    "bd_engagement_letter_department_id_fkey",
                    "qlk_task_department_id_fkey",
                    "qlk_user_department_rel_user_id_fkey",
                    "qlk_user_department_rel_department_id_fkey",
                    "qlk_user_manager_department_rel_user_id_fkey",
                    "qlk_user_manager_department_rel_department_id_fkey",
                    "qlk_user_member_department_rel_user_id_fkey",
                    "qlk_user_member_department_rel_department_id_fkey",
                    "qlk_arbitration_case_department_id_fkey",
                    "qlk_case_department_id_fkey",
                    "qlk_corporate_case_department_id_fkey",
                ],
            ),
        )
        cr.execute(
            """
            DELETE FROM ir_model_relation
             WHERE name IN (
                   'qlk_user_department_rel',
                   'qlk_user_manager_department_rel',
                   'qlk_user_member_department_rel'
             )
            """
        )
        cr.execute(
            "DELETE FROM ir_model_fields WHERE model = ANY(%s)",
            (list(self.OBSOLETE_MODELS),),
        )
        cr.execute(
            "DELETE FROM ir_model WHERE model = ANY(%s)",
            (list(self.OBSOLETE_MODELS),),
        )
        cr.execute(
            "DELETE FROM ir_model_data WHERE model = ANY(%s)",
            (list(self.OBSOLETE_MODELS),),
        )
        for model, fields in self.REMOVED_FIELD_METADATA.items():
            cr.execute(
                "DELETE FROM ir_model_fields WHERE model = %s AND name = ANY(%s)",
                (model, list(fields)),
            )
            cr.execute(
                """
                DELETE FROM ir_model_data
                 WHERE model = 'ir.model.fields'
                   AND name = ANY(%s)
                """,
                ([
                    "field_%s__%s" % (model.replace(".", "_"), field_name)
                    for field_name in fields
                ],),
            )
        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE module = 'qlk_management'
               AND (
                    name LIKE 'access_project_transfer%%'
                 OR name LIKE 'access_project_create_litigation_case%%'
                 OR name LIKE 'field_qlk_department%%'
                 OR name LIKE 'model_qlk_department%%'
                 OR name LIKE 'access_qlk_department%%'
                 OR name LIKE 'rule_qlk_department%%'
                 OR name IN ('model_qlk_user_department_role',
                             'access_qlk_user_department_role_admin',
                             'access_qlk_user_department_role_qlk_admin',
                             'module_qlk_department_access',
                             'department_litigation',
                             'department_corporate',
                             'department_arbitration',
                             'department_mp',
                             'group_qlk_department_user',
                             'group_qlk_department_manager',
                             'view_qlk_department_list',
                             'view_qlk_department_form',
                             'action_qlk_department',
                             'menu_qlk_department_access')
               )
            """
        )
