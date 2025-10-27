# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class NotoNotificationItem(models.Model):
    _name = "noto.notification.item"
    _description = "Noto Actionable Notification"
    _order = "priority desc, due_datetime asc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    notification_type = fields.Selection(
        selection=lambda self: self._selection_notification_type(),
        string="Record Type",
        required=True,
        default="session",
        tracking=True,
    )
    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "Normal"),
            ("2", "High"),
        ],
        default="1",
        string="Priority",
    )
    due_datetime = fields.Datetime(
        string="Reminder Time",
        required=True,
        tracking=True,
    )
    grace_minutes = fields.Integer(
        string="Grace Minutes",
        default=0,
        help="Keep the notification active for the provided minutes after the due time.",
    )
    state = fields.Selection(
        [
            ("pending", "Awaiting Action"),
            ("snoozed", "Snoozed"),
            ("done", "Handled"),
        ],
        default="pending",
        tracking=True,
    )
    sticky_ack_required = fields.Boolean(
        string="Manual Dismissal",
        default=True,
        help="When enabled the UI banner stays visible until a button is clicked.",
    )
    need_sound = fields.Boolean(
        string="Play Sound",
        default=True,
        help="Trigger a device sound every time the reminder is due.",
    )
    reference_model_id = fields.Many2one(
        "ir.model",
        string="Linked Model",
        help="Used to open the related record directly from the notification.",
    )
    reference_res_id = fields.Integer(string="Record ID")
    reference_display_name = fields.Char(
        string="Record Label",
        compute="_compute_reference_display_name",
        store=True,
    )
    note = fields.Text(string="Operational Note")
    action_url = fields.Char(
        string="Fallback URL",
        help="Optional URL opened when clicking the action button in the sticky banner.",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    is_due = fields.Boolean(
        compute="_compute_is_due",
        store=False,
    )
    due_in_minutes = fields.Integer(
        compute="_compute_due_in_minutes",
        store=False,
    )
    last_alert_at = fields.Datetime(string="Last Alerted At", readonly=True, copy=False)
    acknowledgement_uid = fields.Many2one(
        "res.users",
        string="Acknowledged By",
        readonly=True,
        copy=False,
    )

    _sql_constraints = [
        (
            "due_datetime_positive",
            "CHECK(due_datetime IS NOT NULL)",
            "A reminder needs a due datetime.",
        )
    ]

    # -------------------------------------------------------------------------
    # Helper selections & computes
    # -------------------------------------------------------------------------
    @api.model
    def _selection_notification_type(self):
        return [
            ("session", "Session"),
            ("case", "Case"),
            ("consultation", "Consultation"),
            ("report", "Report"),
            ("payment", "Payment"),
            ("cheque", "Cheque"),
            ("custom", "Custom"),
        ]

    @api.depends("reference_model_id", "reference_res_id")
    def _compute_reference_display_name(self):
        for record in self:
            display_name = False
            if record.reference_model_id and record.reference_res_id:
                try:
                    linked = self.env[record.reference_model_id.model].browse(
                        record.reference_res_id
                    )
                    if linked.exists():
                        display_name = linked.display_name
                except Exception:
                    display_name = False
            record.reference_display_name = display_name

    @api.depends("due_datetime", "grace_minutes", "state")
    def _compute_is_due(self):
        now = fields.Datetime.now()
        for record in self:
            deadline = record.due_datetime
            if record.grace_minutes:
                deadline = deadline + timedelta(minutes=record.grace_minutes)
            record.is_due = bool(
                record.state == "pending"
                and record.due_datetime
                and deadline
                and deadline <= now
            )

    @api.depends("due_datetime")
    def _compute_due_in_minutes(self):
        now = fields.Datetime.now()
        for record in self:
            if record.due_datetime:
                delta = record.due_datetime - now
                record.due_in_minutes = int(delta.total_seconds() // 60)
            else:
                record.due_in_minutes = 0

    # -------------------------------------------------------------------------
    # CRUD overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            due = vals.get("due_datetime")
            if not due:
                raise UserError(_("A reminder time is required."))
            if vals.get("state") == "done":
                vals.setdefault("acknowledgement_uid", self.env.user.id)
        records = super().create(vals_list)
        records._notify_bus()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(
            field in vals
            for field in ["state", "due_datetime", "reference_res_id", "reference_model_id"]
        ):
            self._notify_bus()
        return res

    # -------------------------------------------------------------------------
    # Business logic
    # -------------------------------------------------------------------------
    def action_mark_done(self):
        for record in self:
            if record.state == "done":
                continue
            record.write(
                {
                    "state": "done",
                    "acknowledgement_uid": self.env.user.id,
                    "last_alert_at": fields.Datetime.now(),
                }
            )
        return True

    def action_snooze(self, minutes=15):
        now = fields.Datetime.now()
        for record in self:
            base_time = record.due_datetime or now
            if base_time < now:
                base_time = now
            new_time = base_time + timedelta(minutes=minutes)
            record.write(
                {
                    "due_datetime": new_time,
                    "state": "snoozed",
                    "last_alert_at": now,
                }
            )
            record.message_post(body=_("Reminder snoozed for %s minutes.") % minutes)
        return True

    def action_reset_pending(self):
        self.write({"state": "pending"})
        self._notify_bus()
        return True

    def action_open_target(self):
        self.ensure_one()
        if not (self.reference_model_id and self.reference_res_id):
            raise UserError(_("No related record was provided."))
        return {
            "type": "ir.actions.act_window",
            "res_model": self.reference_model_id.model,
            "res_id": self.reference_res_id,
            "view_mode": "form",
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # RPC helpers
    # -------------------------------------------------------------------------
    @api.model
    def get_due_notifications(self):
        """Called by the JS sticky component to render the banner."""
        now = fields.Datetime.now()
        domain = [
            ("state", "in", ["pending", "snoozed"]),
            ("due_datetime", "<=", now),
        ]
        records = self.search(domain, order="priority desc, due_datetime asc", limit=10)
        records.filtered(lambda r: r.state == "snoozed").write({"state": "pending"})
        records.write({"last_alert_at": now})
        type_selection = dict(self._fields["notification_type"]._description_selection(self.env))
        payload = []
        for record in records:
            payload.append(
                {
                    "id": record.id,
                    "name": record.name,
                    "type_label": type_selection.get(record.notification_type, record.notification_type),
                    "due": fields.Datetime.to_string(record.due_datetime),
                    "record_name": record.reference_display_name,
                    "note": record.note,
                    "need_sound": record.need_sound,
                    "sticky_ack_required": record.sticky_ack_required,
                }
            )
        return payload

    @api.model
    def take_action(self, record_id, action):
        record = self.browse(record_id).exists()
        if not record:
            raise UserError(_("Notification not found."))
        if action == "done":
            record.action_mark_done()
        elif action == "snooze":
            record.action_snooze()
        elif action == "open":
            return record.action_open_target()
        else:
            raise UserError(_("Unknown action: %s") % action)
        return True

    # -------------------------------------------------------------------------
    # Internal utilities
    # -------------------------------------------------------------------------
    def _notify_bus(self):
        if not self:
            return
        bus_bus = self.env["bus.bus"]
        for notification in self:
            bus_bus._sendone(
                "notification.refresh",
                "notification",
                {"notification_id": notification.id},
            )
