# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


SYNC_MODELS = [
    "qlk.case",
    "qlk.hearing",
    "qlk.memo",
    "qlk.work",
    "qlk.implementation.procedure",
]


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model_name in SYNC_MODELS:
        if model_name not in env:
            continue
        field_name = env[model_name]._get_notification_reference_field() if hasattr(env[model_name], "_get_notification_reference_field") else "reminder_date"
        if field_name not in env[model_name]._fields:
            continue
        records = env[model_name].search([(field_name, "!=", False)])
        if records:
            records._sync_notification_item()
