from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestProjectTaskAllocatedHours(TransactionCase):
    def _create_task(self, allocated_hours):
        return self.env["project.task"].create(
            {
                "name": "Allocated Hours Test",
                "allocated_hours": allocated_hours,
            }
        )

    def test_sub_hour_allocated_hours_are_valid(self):
        # These values are the float-hour equivalents of HH:MM:SS user input.
        examples = {
            "00:00:30": 30 / 3600,
            "00:04:00": 4 / 60,
            "00:30:00": 0.5,
            "01:00:00": 1.0,
            "02:15:30": 2 + 15 / 60 + 30 / 3600,
        }
        for label, allocated_hours in examples.items():
            task = self._create_task(allocated_hours)
            self.assertAlmostEqual(
                task.allocated_hours,
                allocated_hours,
                places=6,
                msg=f"{label} should be accepted and stored as float hours",
            )

    def test_zero_allocated_hours_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_task(0.0)

    def test_kanban_default_user_id_populates_assignees(self):
        defaults = self.env["project.task"].with_context(default_user_id=self.env.user.id).default_get(["user_ids"])
        user_ids = self.env["project.task"]._fields["user_ids"].convert_to_cache(
            defaults.get("user_ids", []),
            self.env["project.task"],
        )
        self.assertIn(self.env.user.id, user_ids)

    def test_single_kanban_user_id_is_saved_as_assignee(self):
        task = self.env["project.task"].create(
            {
                "name": "Kanban Assignee Test",
                "allocated_hours": 0.5,
                "user_id": self.env.user.id,
            }
        )
        self.assertIn(self.env.user, task.user_ids)

    def test_task_hours_line_uses_hours_spent_as_required_hours(self):
        employee = self.env["hr.employee"].create({"name": "Task Hours Employee"})
        task = self.env["qlk.task"].create(
            {
                "name": "Task Hours Line",
                "department": "management",
                "employee_id": employee.id,
                "hours_spent": 4 / 60,
                "date_start": fields.Date.today(),
            }
        )
        self.assertAlmostEqual(task.required_hours, 4 / 60, places=6)

    def test_legacy_working_hours_syncs_required_and_work_hours(self):
        task = self.env["task"].create(
            {
                "name": "Legacy Working Hours",
                "required_hours": 30 / 60,
            }
        )
        self.assertAlmostEqual(task.work_hours, 30 / 60, places=6)
