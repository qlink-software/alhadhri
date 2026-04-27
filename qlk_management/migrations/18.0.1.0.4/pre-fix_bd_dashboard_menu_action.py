# -*- coding: utf-8 -*-


def migrate(cr, version):
    cr.execute(
        """
        WITH existing AS (
            SELECT id
              FROM ir_act_client
             WHERE tag = 'qlk.bd.dashboard'
             LIMIT 1
        ),
        inserted AS (
            INSERT INTO ir_act_client (
                type,
                binding_type,
                binding_view_types,
                name,
                tag,
                target,
                context,
                create_uid,
                write_uid,
                create_date,
                write_date
            )
            SELECT 'ir.actions.client',
                   'action',
                   'list,form',
                   '{"en_US": "Business Development Dashboard"}'::jsonb,
                   'qlk.bd.dashboard',
                   'main',
                   '{}',
                   1,
                   1,
                   now(),
                   now()
             WHERE NOT EXISTS (SELECT 1 FROM existing)
            RETURNING id
        ),
        chosen AS (
            SELECT id FROM existing
            UNION ALL
            SELECT id FROM inserted
            LIMIT 1
        ),
        imd_update AS (
            UPDATE ir_model_data
               SET model = 'ir.actions.client',
                   res_id = (SELECT id FROM chosen),
                   noupdate = false,
                   write_date = now()
             WHERE module = 'qlk_management'
               AND name = 'action_bd_dashboard'
            RETURNING id
        ),
        imd_insert AS (
            INSERT INTO ir_model_data (
                module,
                name,
                model,
                res_id,
                noupdate,
                create_uid,
                write_uid,
                create_date,
                write_date
            )
            SELECT 'qlk_management',
                   'action_bd_dashboard',
                   'ir.actions.client',
                   (SELECT id FROM chosen),
                   false,
                   1,
                   1,
                   now(),
                   now()
             WHERE NOT EXISTS (SELECT 1 FROM imd_update)
            RETURNING id
        ),
        bd_menus AS (
            SELECT res_id AS id
              FROM ir_model_data
             WHERE module = 'qlk_management'
               AND model = 'ir.ui.menu'
               AND name IN ('menu_management_root', 'menu_bd_dashboard')
        )
        UPDATE ir_ui_menu
           SET action = 'ir.actions.client,' || (SELECT id FROM chosen),
               write_uid = 1,
               write_date = now()
         WHERE id IN (SELECT id FROM bd_menus)
            OR action = 'ir.actions.client,700'
        """
    )
    cr.execute(
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
    )
