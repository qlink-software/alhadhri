# -*- coding: utf-8 -*-


OBSOLETE_MODELS = [
    "qlk.project",
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
]

OBSOLETE_XML_NAMES = [
    "action_project_dashboard",
    "action_qlk_project",
    "action_qlk_project_tasks",
    "action_qlk_project_hours",
    "action_qlk_project_stage",
    "action_qlk_project_litigation",
    "action_qlk_project_corporate",
    "action_qlk_project_arbitration",
    "menu_qlk_project_projects",
    "menu_qlk_project_projects_list",
    "menu_qlk_project_working_hours",
    "menu_qlk_project_tasks",
    "menu_qlk_project_hours",
    "menu_qlk_project_stages",
    "menu_qlk_project_dashboards_root",
    "menu_project_dashboard_entry",
    "menu_qlk_project_analytics_dashboard",
]


def migrate(cr, version):
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'qlk_management'
           AND model = 'ir.ui.menu'
           AND name = ANY(%s)
        """,
        (OBSOLETE_XML_NAMES,),
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
        (OBSOLETE_MODELS, OBSOLETE_MODELS),
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
    cr.execute("DELETE FROM ir_act_window WHERE res_model = ANY(%s)", (OBSOLETE_MODELS,))
    cr.execute(
        """
        DELETE FROM ir_act_client
         WHERE tag = 'qlk.project.dashboard'
            OR res_model = ANY(%s)
        """,
        (OBSOLETE_MODELS,),
    )
