# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class LawyerAssignmentNotificationMixin(models.AbstractModel):
    _name = "qlk.lawyer.assignment.notification.mixin"
    _description = "Lawyer Assignment Notification Helpers"

    def _notification_users_from_employees(self, employees):
        return employees.mapped("user_id").filtered("active")

    def _project_type_label(self, project):
        return dict(project._fields["service_category"].selection).get(
            project.service_category,
            project.service_category or project.service_type or "-",
        )

    def _notify_project_assignment(self, users):
        center = self.env["qlk.lawyer.notification"]
        for project in self:
            recipients = users if len(self) == 1 else (
                project.lawyer_id.user_id | project.responsible_user_ids
            )
            if not recipients:
                continue
            body = _(
                """
                <p>Dear Lawyer,</p>
                <p>A new project has been assigned to you.</p>
                <p><b>Service Code:</b> %(code)s<br/>
                <b>Client:</b> %(client)s<br/>
                <b>Project:</b> %(project)s<br/>
                <b>Project Type:</b> %(project_type)s<br/>
                <b>Assigned By:</b> %(assigned_by)s<br/>
                <b>Date:</b> %(date)s</p>
                <p>Please review and start working on the project.</p>
                <p>Regards,<br/>Al Hadhri &amp; Partners</p>
                """
            ) % {
                "code": project.service_code or "-",
                "client": project.client_id.display_name or "-",
                "project": project.name or project.service_code or "-",
                "project_type": self._project_type_label(project),
                "assigned_by": self.env.user.display_name,
                "date": fields.Datetime.to_string(fields.Datetime.now()),
            }
            center.notify(
                project,
                recipients,
                "project",
                _("New Project Assigned To You"),
                body,
                project=project,
            )

    def _case_notification_users(self, record):
        employees = self.env["hr.employee"]
        users = self.env["res.users"]
        if "employee_id" in record._fields:
            employees |= record.employee_id
        if "employee_ids" in record._fields:
            employees |= record.employee_ids
        if "responsible_employee_id" in record._fields:
            employees |= record.responsible_employee_id
        if record.project_id:
            employees |= record.project_id.lawyer_id
            users |= record.project_id.responsible_user_ids
        return users | self._notification_users_from_employees(employees)

    def _notify_case_assignment(self, users=False):
        center = self.env["qlk.lawyer.notification"]
        for record in self:
            recipients = users or self._case_notification_users(record)
            if not recipients:
                continue
            degree = (
                record.litigation_degree_id.display_name
                if "litigation_degree_id" in record._fields and record.litigation_degree_id
                else "-"
            )
            client = (
                record.client_id.display_name
                if "client_id" in record._fields and record.client_id
                else record.project_id.client_id.display_name
            )
            case_type = (
                record._description
                or dict(record._fields.get("service_category", fields.Selection()).selection).get(
                    getattr(record, "service_category", False), "-"
                )
            )
            body = _(
                """
                <p>Dear Lawyer,</p>
                <p>A new case has been created and assigned to you.</p>
                <p><b>Case Number:</b> %(case_number)s<br/>
                <b>Project:</b> %(project)s<br/>
                <b>Client:</b> %(client)s<br/>
                <b>Case Type:</b> %(case_type)s<br/>
                <b>Degree:</b> %(degree)s</p>
                <p>Please review the case immediately.</p>
                <p>Regards,<br/>Al Hadhri &amp; Partners</p>
                """
            ) % {
                "case_number": getattr(record, "case_number", False)
                or getattr(record, "service_code", False)
                or record.display_name,
                "project": record.project_id.service_code or record.project_id.display_name,
                "client": client or "-",
                "case_type": case_type or "-",
                "degree": degree,
            }
            center.notify(
                record,
                recipients,
                "case",
                _("New Case Assigned To You"),
                body,
                project=record.project_id,
                case=record if record._name == "qlk.case" else False,
            )


class QlkProject(models.Model):
    _name = "qlk.project"
    _inherit = ["qlk.project", "qlk.lawyer.assignment.notification.mixin"]

    def _notify_project_created(self):
        for project in self:
            project._notify_project_assignment(
                project.lawyer_id.user_id | project.responsible_user_ids
            )
        return True

    def write(self, vals):
        previous_users = {
            project.id: set((project.lawyer_id.user_id | project.responsible_user_ids).ids)
            for project in self
        }
        result = super().write(vals)
        if {"lawyer_id", "responsible_user_ids"}.intersection(vals):
            for project in self:
                new_users = (project.lawyer_id.user_id | project.responsible_user_ids).filtered(
                    lambda user: user.id not in previous_users[project.id]
                )
                if new_users:
                    project._notify_project_assignment(new_users)
        return result


class QlkCase(models.Model):
    _name = "qlk.case"
    _inherit = ["qlk.case", "qlk.lawyer.assignment.notification.mixin"]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_case_assignment()
        return records

    def write(self, vals):
        previous_users = {record.id: set(record._case_notification_users(record).ids) for record in self}
        result = super().write(vals)
        if {"employee_id", "employee_ids", "project_id"}.intersection(vals):
            for record in self:
                new_users = record._case_notification_users(record).filtered(
                    lambda user: user.id not in previous_users[record.id]
                )
                if new_users:
                    record._notify_case_assignment(new_users)
        return result


class CorporateCase(models.Model):
    _name = "qlk.corporate.case"
    _inherit = ["qlk.corporate.case", "qlk.lawyer.assignment.notification.mixin"]

    def _notify_responsible_user(self, message):
        self._notify_case_assignment()
        return True


class ArbitrationCase(models.Model):
    _name = "qlk.arbitration.case"
    _inherit = ["qlk.arbitration.case", "qlk.lawyer.assignment.notification.mixin"]

    def _notify_responsible_user(self, message):
        self._notify_case_assignment()
        return True


class QlkHearing(models.Model):
    _name = "qlk.hearing"
    _inherit = ["qlk.hearing", "mail.activity.mixin"]

    def _hearing_notification_users(self):
        self.ensure_one()
        employees = self.employee_id | self.employee2_id | self.employee_ids
        if self.case_id:
            employees |= self.case_id.employee_id | self.case_id.employee_ids
        return employees.mapped("user_id").filtered("active")

    def _notify_hearing_assignment(self, users=False):
        center = self.env["qlk.lawyer.notification"]
        for hearing in self:
            recipients = users or hearing._hearing_notification_users()
            if not recipients:
                continue
            body = _(
                """
                <p>Dear Lawyer,</p>
                <p>A hearing has been assigned to you.</p>
                <p><b>Hearing:</b> %(hearing)s<br/>
                <b>Date:</b> %(date)s<br/>
                <b>Case:</b> %(case)s<br/>
                <b>Client:</b> %(client)s</p>
                <p>Please review the hearing details.</p>
                <p>Regards,<br/>Al Hadhri &amp; Partners</p>
                """
            ) % {
                "hearing": hearing.display_name,
                "date": hearing.date or "-",
                "case": hearing.case_id.display_name or "-",
                "client": hearing.case_id.client_id.display_name if hearing.case_id.client_id else "-",
            }
            center.notify(
                hearing,
                recipients,
                "hearing",
                _("New Hearing Assigned To You"),
                body,
                project=hearing.case_id.project_id,
                case=hearing.case_id,
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_hearing_assignment()
        return records

    def write(self, vals):
        previous_users = {hearing.id: set(hearing._hearing_notification_users().ids) for hearing in self}
        result = super().write(vals)
        if {"employee_id", "employee2_id", "employee_ids"}.intersection(vals):
            for hearing in self:
                new_users = hearing._hearing_notification_users().filtered(
                    lambda user: user.id not in previous_users[hearing.id]
                )
                if new_users:
                    hearing._notify_hearing_assignment(new_users)
        return result


class QlkTask(models.Model):
    _inherit = "qlk.task"

    def _send_assignment_email(self):
        center = self.env["qlk.lawyer.notification"]
        for task in self.filtered("assigned_user_id"):
            body = _(
                """
                <p>Dear Lawyer,</p>
                <p>A new task has been assigned to you.</p>
                <p><b>Task:</b> %(task)s<br/>
                <b>Project:</b> %(project)s<br/>
                <b>Deadline:</b> %(deadline)s<br/>
                <b>Assigned By:</b> %(assigned_by)s</p>
                <p>Regards,<br/>Al Hadhri &amp; Partners</p>
                """
            ) % {
                "task": task.display_name,
                "project": task.project_id.service_code if task.project_id else "-",
                "deadline": task.delivery_date or task.date_finished or "-",
                "assigned_by": self.env.user.display_name,
            }
            center.notify(
                task,
                task.assigned_user_id,
                "task",
                _("New Task Assigned To You"),
                body,
                project=task.project_id,
                case=task.case_id,
            )
        return True


class ProjectTask(models.Model):
    _inherit = "project.task"

    def _send_assignment_email(self, users=None):
        center = self.env["qlk.lawyer.notification"]
        for task in self:
            recipients = users or task.user_ids
            if not recipients:
                continue
            body = _(
                """
                <p>Dear Lawyer,</p>
                <p>A new task has been assigned to you.</p>
                <p><b>Task:</b> %(task)s<br/>
                <b>Project:</b> %(project)s<br/>
                <b>Deadline:</b> %(deadline)s<br/>
                <b>Assigned By:</b> %(assigned_by)s</p>
                <p>Regards,<br/>Al Hadhri &amp; Partners</p>
                """
            ) % {
                "task": task.display_name,
                "project": task.qlk_project_id.service_code if task.qlk_project_id else "-",
                "deadline": task.delivery_date or task.date_deadline or "-",
                "assigned_by": self.env.user.display_name,
            }
            center.notify(
                task,
                recipients,
                "task",
                _("New Task Assigned To You"),
                body,
                project=task.qlk_project_id,
                case=task.case_id,
            )
        return True
