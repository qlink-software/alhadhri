# -*- coding: utf-8 -*-
from odoo import _, fields, models

from .reminder_mixin import ReminderNotificationMixin


class CaseReminderNotification(ReminderNotificationMixin, models.Model):
    _inherit = "qlk.case"

    def _get_notification_type(self):
        return "case"

    def _get_notification_name(self):
        self.ensure_one()
        return _("Case Reminder: %s") % (self.display_name or self.name or _("Case"))

    def _get_notification_note(self):
        self.ensure_one()
        details = []
        if self.subject:
            details.append(self.subject)
        if self.employee_id:
            details.append(_("Assigned lawyer: %s") % self.employee_id.name)
        if self.client_id:
            details.append(_("Client: %s") % self.client_id.name)
        return "\n".join(details) if details else False


class HearingReminderNotification(ReminderNotificationMixin, models.Model):
    _inherit = "qlk.hearing"

    def _get_notification_type(self):
        return "session"

    def _get_notification_name(self):
        self.ensure_one()
        base = self.display_name or self.name or _("Hearing")
        if self.date:
            base = "%s (%s)" % (base, fields.Date.to_string(self.date))
        return _("Hearing Reminder: %s") % base

    def _get_notification_note(self):
        self.ensure_one()
        details = []
        if self.case_id:
            details.append(_("Case: %s") % self.case_id.display_name)
        if self.employee_id:
            details.append(_("Lawyer: %s") % self.employee_id.name)
        if self.subject:
            details.append(self.subject)
        return "\n".join(details) if details else False


class MemoReminderNotification(ReminderNotificationMixin, models.Model):
    _inherit = "qlk.memo"

    def _get_notification_type(self):
        return "report"

    def _get_notification_name(self):
        self.ensure_one()
        return _("Memo Reminder: %s") % (self.display_name or self.name or _("Memo"))

    def _get_notification_note(self):
        self.ensure_one()
        if self.case_id:
            return _("Case: %s") % self.case_id.display_name
        return False


class WorkReminderNotification(ReminderNotificationMixin, models.Model):
    _inherit = "qlk.work"

    def _get_notification_type(self):
        return "work"

    def _get_notification_name(self):
        self.ensure_one()
        return _("Work Reminder: %s") % (self.display_name or self.name or _("Work"))

    def _get_notification_note(self):
        self.ensure_one()
        details = []
        if self.case_id:
            details.append(_("Case: %s") % self.case_id.display_name)
        if self.employee_id:
            details.append(_("Lawyer: %s") % self.employee_id.name)
        if self.subject:
            details.append(self.subject)
        return "\n".join(details) if details else False


class ImplementationProcedureReminderNotification(ReminderNotificationMixin, models.Model):
    _inherit = "qlk.implementation.procedure"

    def _get_notification_type(self):
        return "procedure"

    def _get_notification_name(self):
        self.ensure_one()
        return _("Procedure Reminder: %s") % (self.display_name or self.name or _("Procedure"))

    def _get_notification_note(self):
        self.ensure_one()
        details = []
        if self.case_id:
            details.append(_("Case: %s") % self.case_id.display_name)
        if self.employee_id:
            details.append(_("Lawyer: %s") % self.employee_id.name)
        if self.subject:
            details.append(_("Subject: %s") % self.subject.display_name)
        return "\n".join(details) if details else False
