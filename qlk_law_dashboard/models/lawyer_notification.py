# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


_logger = logging.getLogger(__name__)


NOTIFICATION_TYPES = [
    ("project", "Project"),
    ("case", "Case"),
    ("hearing", "Hearing"),
    ("task", "Task"),
    ("daily_summary", "Daily Summary"),
]


class QlkLawyerNotification(models.Model):
    _name = "qlk.lawyer.notification"
    _description = "Lawyer Notification"
    _inherit = ["mail.thread"]
    _order = "notification_date desc, id desc"

    name = fields.Char(string="Notification", required=True, tracking=True)
    user_id = fields.Many2one(
        "res.users",
        string="Lawyer",
        required=True,
        index=True,
        ondelete="cascade",
    )
    notification_type = fields.Selection(
        NOTIFICATION_TYPES,
        string="Type",
        required=True,
        index=True,
    )
    notification_date = fields.Datetime(
        string="Date",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    project_id = fields.Many2one("qlk.project", string="Project", ondelete="set null", index=True)
    case_id = fields.Many2one("qlk.case", string="Case", ondelete="set null", index=True)
    target_model = fields.Char(string="Target Model", required=True, index=True)
    target_res_id = fields.Integer(string="Target Record", required=True, index=True)
    message = fields.Html(string="Message", sanitize=True)
    email_address = fields.Char(string="Email")
    email_sent = fields.Boolean(string="Sent Email", readonly=True, copy=False)
    email_error = fields.Text(string="Email Error", readonly=True, copy=False)
    state = fields.Selection(
        [("unread", "Unread"), ("read", "Read")],
        string="Read Status",
        default="unread",
        required=True,
        index=True,
        tracking=True,
    )
    read_date = fields.Datetime(string="Read Date", readonly=True, copy=False)
    read_by_id = fields.Many2one("res.users", string="Read By", readonly=True, copy=False)
    assigned_by_id = fields.Many2one(
        "res.users",
        string="Assigned By",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )

    def _check_notification_owner(self):
        if self.env.is_superuser() or self.env.user.has_group(
            "qlk_law_dashboard.group_qlk_law_dashboard_manager"
        ):
            return
        if any(notification.user_id != self.env.user for notification in self):
            raise AccessError(_("You can only access your own notifications."))

    def action_mark_read(self):
        self._check_notification_owner()
        unread = self.filtered(lambda notification: notification.state != "read")
        if unread:
            unread.sudo().write(
                {
                    "state": "read",
                    "read_date": fields.Datetime.now(),
                    "read_by_id": self.env.user.id,
                }
            )
        return True

    def action_open_target(self):
        self.ensure_one()
        self._check_notification_owner()
        self.action_mark_read()
        if not self.target_model or not self.target_res_id or self.target_model not in self.env:
            return False
        target = self.env[self.target_model].browse(self.target_res_id).exists()
        if not target:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": self.target_model,
            "res_id": target.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _email_address(self, user):
        return user.partner_id.email or user.email or ""

    @api.model
    def _email_from(self):
        mail_server = self.env["ir.mail_server"].sudo().search(
            [("active", "=", True), ("smtp_user", "!=", False)],
            order="sequence, id",
            limit=1,
        )
        return (
            mail_server.smtp_user
            or self.env.company.partner_id.email_formatted
            or self.env.user.partner_id.email_formatted
            or self.env.user.email
        )

    @api.model
    def _create_delivery_log(self, notification, error):
        return self.env["qlk.notification.delivery.log"].sudo().create(
            {
                "notification_id": notification.id,
                "user_id": notification.user_id.id,
                "email": notification.email_address,
                "delivery_date": fields.Datetime.now(),
                "error": str(error),
            }
        )

    @api.model
    def _send_email(self, notification, subject, body_html):
        if not notification.email_address:
            error = _("The assigned lawyer does not have an email address.")
            notification.sudo().write({"email_error": error})
            self._create_delivery_log(notification, error)
            return False
        mail = self.env["mail.mail"].sudo().create(
            {
                "subject": subject,
                "body_html": body_html,
                "email_to": notification.email_address,
                "email_from": self._email_from(),
                "auto_delete": False,
            }
        )
        try:
            mail.send(raise_exception=True)
            notification.sudo().write({"email_sent": True, "email_error": False})
            return True
        except Exception as error:  # The internal notification must survive SMTP failures.
            _logger.exception("Lawyer notification email delivery failed")
            notification.sudo().write({"email_sent": False, "email_error": str(error)})
            self._create_delivery_log(notification, error)
            return False

    @api.model
    def _create_activity(self, source, user, subject, body_html):
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        model = self.env["ir.model"].sudo()._get(source._name)
        if not activity_type or not model:
            return False
        existing = self.env["mail.activity"].sudo().search(
            [
                ("res_model_id", "=", model.id),
                ("res_id", "=", source.id),
                ("user_id", "=", user.id),
                ("summary", "=", subject),
            ],
            limit=1,
        )
        if existing:
            return existing
        return self.env["mail.activity"].sudo().create(
            {
                "activity_type_id": activity_type.id,
                "res_model_id": model.id,
                "res_id": source.id,
                "user_id": user.id,
                "summary": subject,
                "note": body_html,
            }
        )

    @api.model
    def notify(
        self,
        source,
        users,
        notification_type,
        subject,
        body_html,
        project=False,
        case=False,
    ):
        source.ensure_one()
        users = users.filtered(lambda user: user.active and user.partner_id)
        notifications = self.browse()
        for user in users:
            notification = self.sudo().create(
                {
                    "name": subject,
                    "user_id": user.id,
                    "notification_type": notification_type,
                    "project_id": project.id if project else False,
                    "case_id": case.id if case else False,
                    "target_model": source._name,
                    "target_res_id": source.id,
                    "message": body_html,
                    "email_address": self._email_address(user),
                    "assigned_by_id": self.env.user.id,
                }
            )
            notifications |= notification
            source.sudo().message_subscribe(partner_ids=user.partner_id.ids, subtype_ids=None)
            source.sudo().message_post(
                subject=subject,
                body=Markup(body_html),
                partner_ids=user.partner_id.ids,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
            self._create_activity(source, user, subject, body_html)
            self._send_email(notification, subject, body_html)
        return notifications

    @api.model
    def cron_daily_lawyer_reminder(self):
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        today_start = fields.Datetime.to_datetime(today)
        tomorrow_start = fields.Datetime.to_datetime(tomorrow)
        users = self.env["res.users"].sudo().search(
            [
                ("active", "=", True),
                ("employee_ids", "!=", False),
            ]
        )
        for user in users:
            employee_ids = user.employee_ids.ids
            project_domain = [
                ("notification_type", "=", "project"),
                ("user_id", "=", user.id),
                ("notification_date", ">=", today_start),
                ("notification_date", "<", tomorrow_start),
            ]
            case_domain = [
                ("notification_type", "=", "case"),
                ("user_id", "=", user.id),
                ("notification_date", ">=", today_start),
                ("notification_date", "<", tomorrow_start),
            ]
            hearing_domain = [
                ("date", "=", today),
                "|",
                "|",
                ("employee_id", "in", employee_ids),
                ("employee2_id", "in", employee_ids),
                ("employee_ids", "in", employee_ids),
            ]
            task_domain = [
                ("assigned_user_id", "=", user.id),
                "|",
                "&",
                ("delivery_date", ">=", today_start),
                ("delivery_date", "<", tomorrow_start),
                ("date_finished", "=", today),
            ]
            projects = self.search_count(project_domain)
            cases = self.search_count(case_domain)
            hearings = self.env["qlk.hearing"].sudo().search_count(hearing_domain)
            tasks = self.env["qlk.task"].sudo().search_count(task_domain)
            if not any((projects, cases, hearings, tasks)):
                continue
            body = _(
                """
                <p>Dear Lawyer,</p>
                <p>Today's assigned work summary:</p>
                <ul>
                    <li>Projects assigned today: %(projects)s</li>
                    <li>Cases assigned today: %(cases)s</li>
                    <li>Hearings today: %(hearings)s</li>
                    <li>Tasks due today: %(tasks)s</li>
                </ul>
                <p>Regards,<br/>Al Hadhri &amp; Partners</p>
                """
            ) % {
                "projects": projects,
                "cases": cases,
                "hearings": hearings,
                "tasks": tasks,
            }
            source = user.partner_id
            self.notify(
                source,
                user,
                "daily_summary",
                _("Today's Assigned Work Summary"),
                body,
            )
        return True


class QlkNotificationDeliveryLog(models.Model):
    _name = "qlk.notification.delivery.log"
    _description = "Notification Delivery Log"
    _order = "delivery_date desc, id desc"

    notification_id = fields.Many2one(
        "qlk.lawyer.notification",
        string="Notification",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one("res.users", string="User", required=True, index=True)
    email = fields.Char(string="Email")
    delivery_date = fields.Datetime(string="Date", required=True, default=fields.Datetime.now)
    error = fields.Text(string="Error", required=True)
