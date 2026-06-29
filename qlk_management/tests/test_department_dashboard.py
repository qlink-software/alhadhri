from odoo import Command
from odoo.tests.common import TransactionCase


class TestDepartmentDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {
                "name": "Department Dashboard User",
                "login": "department-dashboard-user-test",
                "groups_id": [
                    Command.link(cls.env.ref("qlk_corporate.group_corporate_manager").id),
                    Command.link(cls.env.ref("qlk_arbitration.group_arbitration_manager").id),
                ],
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Department Dashboard Employee", "user_id": cls.user.id}
        )
        cls.dashboard = cls.env["qlk.department.dashboard"].with_user(cls.user)

    def test_manager_dashboard_remains_personal(self):
        domain = self.dashboard._personal_domain("qlk.project")
        self.assertIn(("lawyer_id", "in", self.user.employee_ids.ids), domain)
        self.assertNotIn(("create_uid", "=", self.user.id), domain)

    def test_corporate_projects_are_department_scoped(self):
        domain = self.dashboard._project_domain("corporate")
        self.assertIn(("service_category", "=", "corporate"), domain)
        self.assertIn(("service_type", "=", "corporate"), domain)
        self.assertNotIn(("service_type", "=", "arbitration"), domain)
        self.assertIn(("lawyer_id", "in", self.user.employee_ids.ids), domain)

    def test_arbitration_projects_are_department_scoped(self):
        domain = self.dashboard._project_domain("arbitration")
        self.assertIn(("service_category", "=", "arbitration"), domain)
        self.assertIn(("service_type", "=", "arbitration"), domain)
        self.assertNotIn(("service_type", "=", "corporate"), domain)
        self.assertIn(("lawyer_id", "in", self.user.employee_ids.ids), domain)

    def test_tasks_are_personal_and_department_scoped(self):
        domain = self.dashboard._task_domain("corporate")
        self.assertIn(("department", "=", "corporate"), domain)
        self.assertIn(("employee_id", "in", self.user.employee_ids.ids), domain)
