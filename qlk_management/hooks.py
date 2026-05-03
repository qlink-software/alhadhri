# -*- coding: utf-8 -*-


LEGACY_PROJECT_FKEYS = {
    "bd_engagement_letter": (
        "bd_engagement_letter_project_id_fkey",
    ),
    "qlk_case": (
        "qlk_case_project_id_fkey",
    ),
    "qlk_corporate_case": (
        "qlk_corporate_case_project_id_fkey",
    ),
    "qlk_arbitration_case": (
        "qlk_arbitration_case_project_id_fkey",
    ),
    "qlk_pre_litigation": (
        "qlk_pre_litigation_project_id_fkey",
    ),
    "qlk_task": (
        "qlk_task_project_id_fkey",
    ),
}


def _drop_legacy_project_fkeys(cr):
    for table, constraint_names in LEGACY_PROJECT_FKEYS.items():
        for constraint_name in constraint_names:
            cr.execute(
                'ALTER TABLE IF EXISTS "%s" DROP CONSTRAINT IF EXISTS "%s"'
                % (table, constraint_name)
            )


def pre_init_hook(env):
    cr = env.cr if hasattr(env, "cr") else env
    _drop_legacy_project_fkeys(cr)
    tables = (
        "bd_engagement_letter",
        "qlk_case",
        "qlk_corporate_case",
        "qlk_arbitration_case",
        "qlk_pre_litigation",
        "qlk_task",
    )
    for table in tables:
        cr.execute(
            """
            WITH rels AS (
                SELECT to_regclass(%s) AS table_rel,
                       to_regclass('project_project') AS project_rel
            )
            SELECT pg_constraint_record.conname
              FROM pg_constraint pg_constraint_record,
                   rels
             WHERE rels.table_rel IS NOT NULL
               AND rels.project_rel IS NOT NULL
               AND pg_constraint_record.conrelid = rels.table_rel
               AND pg_constraint_record.contype = 'f'
               AND pg_constraint_record.confrelid = rels.project_rel
               AND EXISTS (
                    SELECT 1
                      FROM pg_attribute attribute
                     WHERE attribute.attrelid = rels.table_rel
                       AND attribute.attname = 'project_id'
               )
               AND pg_constraint_record.conkey = ARRAY[
                    (
                        SELECT attribute.attnum
                          FROM pg_attribute attribute
                         WHERE attribute.attrelid = rels.table_rel
                           AND attribute.attname = 'project_id'
                    )
               ]
            """,
            [table],
        )
        for (constraint_name,) in cr.fetchall():
            cr.execute('ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (table, constraint_name))


def post_init_hook(env):
    _drop_legacy_project_fkeys(env.cr)
