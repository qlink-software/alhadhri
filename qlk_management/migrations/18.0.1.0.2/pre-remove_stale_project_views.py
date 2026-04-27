# -*- coding: utf-8 -*-


def migrate(cr, version):
    cr.execute(
        """
        SELECT id
          FROM ir_ui_view
         WHERE model = 'res.users'
           AND arch_db::text LIKE '%%department_role_ids%%'
        """
    )
    view_ids = [row[0] for row in cr.fetchall()]
    if view_ids:
        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE model = 'ir.ui.view'
               AND res_id = ANY(%s)
            """,
            (view_ids,),
        )
        cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (view_ids,))

    obsolete_models = [
        "qlk.user.department.role",
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
    ]
    cr.execute(
        """
        DELETE FROM ir_model_access
         WHERE model_id IN (SELECT id FROM ir_model WHERE model = ANY(%s))
        """,
        (obsolete_models,),
    )
    cr.execute(
        """
        DELETE FROM ir_rule
         WHERE model_id IN (SELECT id FROM ir_model WHERE model = ANY(%s))
        """,
        (obsolete_models,),
    )
    cr.execute("DELETE FROM ir_model_fields WHERE model = ANY(%s)", (obsolete_models,))
