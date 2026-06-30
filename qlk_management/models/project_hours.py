# -*- coding: utf-8 -*-
"""Central project-hour accounting, audit, and source synchronization."""

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero


HOUR_TRACKED_FIELDS = ("planned_hours", "consumed_hours", "approved_hours")
HOUR_SOURCE_SELECTION = [
    ("manual", "Manual"),
    ("timesheet", "Timesheet"),
    ("agreement", "Agreement"),
    ("task_update", "Task Update"),
]


class QlkProjectHourTracking(models.Model):
    """Store an immutable business audit trail for project-hour changes."""

    _name = "qlk.project.hour.tracking"
    _description = "Project Hour Tracking"
    _order = "changed_on desc, id desc"

    project_id = fields.Many2one(
        "qlk.project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    field_name = fields.Selection(
        [
            ("planned_hours", "Planned Hours"),
            ("consumed_hours", "Consumed Hours"),
            ("approved_hours", "Approved Hours"),
        ],
        required=True,
        index=True,
    )
    before_value = fields.Float(string="Before", required=True)
    after_value = fields.Float(string="After", required=True)
    difference = fields.Float(required=True)
    modified_by = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    changed_on = fields.Datetime(
        string="Datetime",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    source = fields.Selection(HOUR_SOURCE_SELECTION, required=True, index=True)

    def write(self, vals):
        """Prevent alteration of the immutable tracking history."""
        raise UserError(_("Project hour tracking entries cannot be modified."))

    def unlink(self):
        """Prevent deletion of the immutable tracking history."""
        raise UserError(_("Project hour tracking entries cannot be deleted."))


class QlkProjectHourAudit(models.Model):
    """Store the mandatory reason attached to manual consumed-hour changes."""

    _name = "qlk.project.hour.audit"
    _description = "Manual Project Hour Audit"
    _order = "changed_on desc, id desc"

    project_id = fields.Many2one(
        "qlk.project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    old_value = fields.Float(string="Old Value", required=True)
    new_value = fields.Float(string="New Value", required=True)
    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    changed_on = fields.Datetime(
        string="Date",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    reason = fields.Text(required=True)

    def write(self, vals):
        """Prevent alteration of manual adjustment evidence."""
        raise UserError(_("Manual hour audit entries cannot be modified."))

    def unlink(self):
        """Prevent deletion of manual adjustment evidence."""
        raise UserError(_("Manual hour audit entries cannot be deleted."))


class QlkProjectHours(models.Model):
    """Provide the authoritative hour ledger for legal projects."""

    _inherit = "qlk.project"

    agreement_hours = fields.Float(
        string="Agreement Hours",
        compute="_compute_agreement_hours",
        store=True,
        compute_sudo=True,
    )
    approved_hours = fields.Float(
        string="Approved Hours",
        compute="_compute_hours",
        store=True,
        compute_sudo=True,
    )
    approved_hours_month = fields.Float(
        string="Approved Hours (Month)",
        compute="_compute_approved_hours_month",
        compute_sudo=True,
    )
    over_agreement_hours = fields.Float(
        string="Over Agreement Hours",
        compute="_compute_hours",
        store=True,
        compute_sudo=True,
    )
    last_hours_update = fields.Datetime(string="Last Hours Update", readonly=True, copy=False)
    last_hours_user_id = fields.Many2one(
        "res.users",
        string="Last Hours User",
        readonly=True,
        copy=False,
    )
    hour_tracking_ids = fields.One2many(
        "qlk.project.hour.tracking",
        "project_id",
        string="Hour Tracking",
        readonly=True,
    )
    hour_audit_ids = fields.One2many(
        "qlk.project.hour.audit",
        "project_id",
        string="Manual Audit Log",
        readonly=True,
    )

    @api.depends(
        "engagement_letter_id",
        "engagement_letter_id.planned_hours",
        "engagement_letter_id.agreed_hours",
        "engagement_letter_id.allocated_hours",
        "engagement_letter_id.estimated_hours",
    )
    def _compute_agreement_hours(self):
        """Resolve agreement hours without overwriting manual project planning."""
        for project in self:
            agreement = project.engagement_letter_id
            project.agreement_hours = (
                agreement.planned_hours
                or agreement.agreed_hours
                or agreement.allocated_hours
                or agreement.estimated_hours
                or 0.0
            ) if agreement else 0.0

    def _read_grouped_hour_totals(self):
        """Return consumed and approved totals in batched aggregation queries."""
        project_ids = self.ids
        consumed = {project_id: 0.0 for project_id in project_ids}
        approved = {project_id: 0.0 for project_id in project_ids}
        if not project_ids:
            return consumed, approved

        timesheet_groups = self.env["project.task"].sudo().read_group(
            [("qlk_project_id", "in", project_ids)],
            ["effective_hours:sum", "qlk_project_id"],
            ["qlk_project_id"],
        )
        for group in timesheet_groups:
            project_ref = group.get("qlk_project_id")
            if project_ref:
                consumed[project_ref[0]] += group.get("effective_hours", 0.0) or 0.0

        task_groups = self.env["qlk.task"].sudo().read_group(
            [
                ("project_id", "in", project_ids),
                ("approval_state", "!=", "rejected"),
            ],
            ["hours_spent:sum", "project_id"],
            ["project_id"],
        )
        for group in task_groups:
            project_ref = group.get("project_id")
            if project_ref:
                consumed[project_ref[0]] += group.get("hours_spent", 0.0) or 0.0

        approved_groups = self.env["qlk.task"].sudo().read_group(
            [
                ("project_id", "in", project_ids),
                ("approval_state", "=", "approved"),
            ],
            ["hours_spent:sum", "project_id"],
            ["project_id"],
        )
        for group in approved_groups:
            project_ref = group.get("project_id")
            if project_ref:
                approved[project_ref[0]] = group.get("hours_spent", 0.0) or 0.0
        return consumed, approved

    @api.depends(
        "planned_hours",
        "manual_consumed_hours",
        "project_task_ids.effective_hours",
        "project_task_ids.timesheet_ids.unit_amount",
        "qlk_task_ids.hours_spent",
        "qlk_task_ids.approval_state",
    )
    def _compute_hours(self):
        """Compute all project hour KPIs from non-overlapping source ledgers."""
        persisted = self.filtered("id")
        consumed_totals, approved_totals = persisted._read_grouped_hour_totals()
        for project in self:
            source_hours = consumed_totals.get(project.id, 0.0)
            consumed = (project.manual_consumed_hours or 0.0) + source_hours
            planned = project.planned_hours or 0.0
            project.consumed_hours = consumed
            project.approved_hours = approved_totals.get(project.id, 0.0)
            project.remaining_hours = planned - consumed
            over_agreement = max(consumed - planned, 0.0)
            project.over_agreement_hours = over_agreement
            # Keep the legacy field synchronized for existing views and reports.
            project.overconsumed_hours = over_agreement
            project.hours_usage_percent = round((consumed / planned) * 100.0, 2) if planned else 0.0
            if over_agreement:
                project.hours_state = "danger"
            elif planned and project.hours_usage_percent >= 80.0:
                project.hours_state = "warning"
            else:
                project.hours_state = "normal"

    def _compute_approved_hours_month(self):
        """Compute current-month approved hours dynamically to avoid stale rollover values."""
        totals = {project_id: 0.0 for project_id in self.ids}
        if self.ids:
            today = fields.Date.context_today(self)
            month_start = today.replace(day=1)
            month_end = month_start + relativedelta(months=1)
            groups = self.env["qlk.task"].sudo().read_group(
                [
                    ("project_id", "in", self.ids),
                    ("approval_state", "=", "approved"),
                    ("date_start", ">=", month_start),
                    ("date_start", "<", month_end),
                ],
                ["hours_spent:sum", "project_id"],
                ["project_id"],
            )
            for group in groups:
                project_ref = group.get("project_id")
                if project_ref:
                    totals[project_ref[0]] = group.get("hours_spent", 0.0) or 0.0
        for project in self:
            project.approved_hours_month = totals.get(project.id, 0.0)

    def _hour_snapshot(self):
        """Return values used to detect source-driven computed-field changes."""
        self.flush_recordset(list(HOUR_TRACKED_FIELDS))
        return {
            project.id: {
                field_name: project[field_name] or 0.0
                for field_name in HOUR_TRACKED_FIELDS
            }
            for project in self
        }

    def _track_hour_changes(self, before, source):
        """Create one immutable tracking row for each changed hour KPI."""
        if not self or self.env.context.get("skip_hour_tracking"):
            return False
        source = source if source in dict(HOUR_SOURCE_SELECTION) else "task_update"
        self.flush_recordset(list(HOUR_TRACKED_FIELDS))
        tracking_values = []
        changed_projects = self.env["qlk.project"]
        for project in self:
            old_values = before.get(project.id, {})
            for field_name in HOUR_TRACKED_FIELDS:
                old_value = old_values.get(field_name, 0.0) or 0.0
                new_value = project[field_name] or 0.0
                if float_is_zero(new_value - old_value, precision_digits=6):
                    continue
                tracking_values.append(
                    {
                        "project_id": project.id,
                        "field_name": field_name,
                        "before_value": old_value,
                        "after_value": new_value,
                        "difference": new_value - old_value,
                        "modified_by": self.env.user.id,
                        "source": source,
                    }
                )
                changed_projects |= project
        if tracking_values:
            self.env["qlk.project.hour.tracking"].sudo().create(tracking_values)
            changed_projects.with_context(skip_hour_tracking=True).write(
                {
                    "last_hours_update": fields.Datetime.now(),
                    "last_hours_user_id": self.env.user.id,
                }
            )
        return bool(tracking_values)

    @api.model_create_multi
    def create(self, vals_list):
        """Require an agreement and record initial agreement-sourced hour values."""
        for vals in vals_list:
            if not vals.get("engagement_letter_id"):
                raise ValidationError(_("Agreement is required when creating a project."))
        projects = super().create(vals_list)
        projects._track_hour_changes(
            {project.id: {field_name: 0.0 for field_name in HOUR_TRACKED_FIELDS} for project in projects},
            "agreement",
        )
        return projects

    def write(self, vals):
        """Track direct planned-hour and manual-ledger updates."""
        if (
            "manual_consumed_hours" in vals
            and not self.env.context.get("manual_consumed_adjustment")
        ):
            raise UserError(
                _("Use Adjust Consumed Hours so the mandatory reason is audited.")
            )
        tracked_input = {"planned_hours", "manual_consumed_hours"}.intersection(vals)
        before = self._hour_snapshot() if tracked_input and not self.env.context.get("skip_hour_tracking") else {}
        result = super().write(vals)
        if before:
            self._track_hour_changes(before, self.env.context.get("hour_change_source", "manual"))
        return result

    def action_adjust_consumed_hours(self):
        """Open the manager-only adjustment wizard with the current total."""
        self.ensure_one()
        if not self.env.is_superuser() and not self.env.user.has_group("qlk_management.group_project_manager"):
            raise UserError(_("Only Project Managers can adjust consumed hours manually."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Adjust Consumed Hours"),
            "res_model": "qlk.project.hour.adjustment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
                "default_new_value": self.consumed_hours,
            },
        }

    def _apply_manual_consumed_hours(self, new_value, reason):
        """Set the requested total through a durable manual offset and audit it."""
        self.ensure_one()
        if not self.env.is_superuser() and not self.env.user.has_group("qlk_management.group_project_manager"):
            raise UserError(_("Only Project Managers can adjust consumed hours manually."))
        if new_value < 0:
            raise ValidationError(_("Consumed Hours cannot be negative."))
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(_("A reason is required for manual consumed-hour changes."))
        old_value = self.consumed_hours
        source_hours = old_value - (self.manual_consumed_hours or 0.0)
        manual_offset = new_value - source_hours
        self.with_context(
            hour_change_source="manual",
            manual_consumed_adjustment=True,
        ).write(
            {"manual_consumed_hours": manual_offset}
        )
        self.env["qlk.project.hour.audit"].sudo().create(
            {
                "project_id": self.id,
                "old_value": old_value,
                "new_value": new_value,
                "user_id": self.env.user.id,
                "reason": reason,
            }
        )
        return True


class AccountAnalyticLineProjectHours(models.Model):
    """Synchronize legal-project KPIs after every timesheet mutation."""

    _inherit = "account.analytic.line"

    @api.model
    def _projects_from_timesheet_vals(self, vals_list):
        """Resolve legal projects referenced by incoming timesheet task values."""
        task_ids = {
            vals.get("task_id")
            for vals in vals_list
            if vals.get("task_id")
        }
        return self.env["project.task"].browse(task_ids).mapped("qlk_project_id")

    @api.model_create_multi
    def create(self, vals_list):
        """Track consumed hours immediately after timesheet creation."""
        projects = self._projects_from_timesheet_vals(vals_list)
        before = projects._hour_snapshot()
        lines = super().create(vals_list)
        projects |= lines.mapped("task_id.qlk_project_id")
        projects._track_hour_changes(before, "timesheet")
        return lines

    def write(self, vals):
        """Track both source and destination projects after timesheet edits."""
        projects = self.mapped("task_id.qlk_project_id")
        if vals.get("task_id"):
            projects |= self.env["project.task"].browse(vals["task_id"]).mapped("qlk_project_id")
        before = projects._hour_snapshot()
        result = super().write(vals)
        projects |= self.mapped("task_id.qlk_project_id")
        projects._track_hour_changes(before, "timesheet")
        return result

    def unlink(self):
        """Track consumed-hour reversal after timesheet deletion."""
        projects = self.mapped("task_id.qlk_project_id")
        before = projects._hour_snapshot()
        result = super().unlink()
        projects._track_hour_changes(before, "timesheet")
        return result


class QlkTaskProjectHours(models.Model):
    """Synchronize consumed and approved hours after legal-task changes."""

    _inherit = "qlk.task"

    @api.model_create_multi
    def create(self, vals_list):
        """Track new task hours against their projects."""
        project_ids = {vals.get("project_id") for vals in vals_list if vals.get("project_id")}
        projects = self.env["qlk.project"].browse(project_ids)
        before = projects._hour_snapshot()
        tasks = super().create(vals_list)
        projects |= tasks.mapped("project_id")
        projects._track_hour_changes(before, "task_update")
        return tasks

    def write(self, vals):
        """Track hour, approval, rejection, and project-link changes."""
        projects = self.mapped("project_id")
        if vals.get("project_id"):
            projects |= self.env["qlk.project"].browse(vals["project_id"])
        before = projects._hour_snapshot()
        result = super().write(vals)
        projects |= self.mapped("project_id")
        projects._track_hour_changes(before, "task_update")
        return result

    def unlink(self):
        """Track consumed and approved reversals after task deletion."""
        projects = self.mapped("project_id")
        before = projects._hour_snapshot()
        result = super().unlink()
        projects._track_hour_changes(before, "task_update")
        return result


class ProjectTaskProjectHours(models.Model):
    """Handle task reassignment or deletion when timesheets already exist."""

    _inherit = "project.task"

    def write(self, vals):
        """Track source-project changes caused by moving a legal task."""
        projects = self.mapped("qlk_project_id")
        if vals.get("case_id"):
            projects |= self.env["qlk.case"].browse(vals["case_id"]).mapped("project_id")
        before = projects._hour_snapshot()
        result = super().write(vals)
        projects |= self.mapped("qlk_project_id")
        projects._track_hour_changes(before, "task_update")
        return result

    def unlink(self):
        """Track timesheet removal caused by deleting a legal project task."""
        projects = self.mapped("qlk_project_id")
        before = projects._hour_snapshot()
        result = super().unlink()
        projects._track_hour_changes(before, "task_update")
        return result
