# -*- coding: utf-8 -*-
from odoo import _, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def notify_warning(self, message, title=None, sticky=False):
        """Send a warning notification to the current user's bus channel when available."""
        if not message:
            return
        payload = {
            "message": message,
            "type": "warning",
            "sticky": bool(sticky),
        }
        if title:
            payload["title"] = title
        if "bus.bus" in self.env:
            for user in self:
                if user.partner_id:
                    self.env["bus.bus"]._sendone(user.partner_id, "display_notification", payload)
            return
        # Fallback: log on partner record when bus is not available.
        for user in self:
            if user.partner_id:
                user.partner_id.message_post(body=message, subject=title or _("Warning"))
