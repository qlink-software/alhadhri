# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ReminderNotificationMixin(models.AbstractModel):
    _name = "noto.reminder.mixin"
    _description = "Reminder -> Notification synchronisation"

    notification_item_id = fields.Many2one(
        "noto.notification.item",
        string="Reminder Notification",
        copy=False,
        readonly=False,
    )

    def _get_notification_reference_field(self):
        return "reminder_date"

    def _get_notification_type(self):
        return "custom"

    def _get_notification_name(self):
        self.ensure_one()
        return self.display_name or _("Reminder")

    def _get_notification_note(self):
        return False

    def _get_notification_priority(self):
        return "1"

    def _get_notification_sound(self):
        return True

    def _get_notification_sticky(self):
        return True

    def _prepare_notification_vals(self):
        self.ensure_one()
        field_name = self._get_notification_reference_field()
        if field_name not in self._fields:
            return False
        reminder = self[field_name]
        if not reminder:
            return False
        model = self.env["ir.model"]._get(self._name)
        return {
            "name": self._get_notification_name(),
            "notification_type": self._get_notification_type(),
            "due_datetime": reminder,
            "priority": self._get_notification_priority(),
            "reference_model_id": model.id,
            "reference_res_id": self.id,
            "reference_field_name": field_name,
            "note": self._get_notification_note(),
            "need_sound": self._get_notification_sound(),
            "sticky_ack_required": self._get_notification_sticky(),
        }

    def _sync_notification_item(self):
        Notification = self.env["noto.notification.item"]
        for record in self:
            field_name = record._get_notification_reference_field()
            if field_name not in record._fields:
                continue
            vals = record._prepare_notification_vals()
            notification = record.notification_item_id
            if vals:
                if notification:
                    update_vals = {
                        key: val
                        for key, val in vals.items()
                        if notification[key] != val
                    }
                    if update_vals:
                        notification.write(update_vals)
                else:
                    notification = Notification.create(vals)
                    record.notification_item_id = notification.id
            else:
                if notification:
                    notification.action_mark_done()
                    notification.unlink()
                    record.notification_item_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_notification_item()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("noto_skip_sync"):
            self._sync_notification_item()
        return res

    def unlink(self):
        notifications = self.notification_item_id
        res = super().unlink()
        if notifications:
            notifications.action_mark_done()
            notifications.unlink()
        return res
