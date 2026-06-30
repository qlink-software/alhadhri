# -*- coding: utf-8 -*-
"""Regression coverage for legal project numbering and hour accounting."""

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestLegalProjectHours(TransactionCase):
    """Validate litigation numbering, degree boundaries, and live hour updates."""

    @classmethod
    def setUpClass(cls):
        """Create an isolated L-109 agreement and three projects."""
        super().setUpClass()
        cls.Project = cls.env["qlk.project"]
        cls.Tracking = cls.env["qlk.project.hour.tracking"]

        # A production clone can already contain L-109. Move only the client-file
        # code inside the test transaction so the exact acceptance example can be
        # exercised; all changes are rolled back with the test class transaction.
        conflicts = cls.env["qlk.client.file"].sudo().search(
            [("litigation_client_code", "=", "L-109")]
        )
        cls.legacy_litigation_codes = {
            project.id: project.service_code
            for project in conflicts.mapped("project_ids")
        }
        for conflict in conflicts:
            conflict.with_context(skip_client_code_lock=True).write(
                {"litigation_client_code": "L-TEST-LEGACY-%s" % conflict.id}
            )

        cls.client = cls.env["res.partner"].create(
            {
                "name": "Legal Project Hours Test Client",
                "customer_rank": 1,
                "identity_type": "other",
                "identity_number": "LEGAL-PROJECT-HOURS-TEST",
            }
        )
        cls.opponent = cls.env["res.partner"].create(
            {"name": "Legal Project Hours Test Opponent"}
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Legal Project Hours Test Lawyer"}
        )
        cls.litigation_service = cls.env["qlk.legal.service.type"].search(
            [("code", "=", "litigation")], limit=1
        )
        cls.degree_f = cls.env["qlk.litigation.degree"].search(
            [("code", "=", "F")], limit=1
        )
        cls.degree_a = cls.env["qlk.litigation.degree"].search(
            [("code", "=", "A")], limit=1
        )
        cls.degree_c = cls.env["qlk.litigation.degree"].search(
            [("code", "=", "C")], limit=1
        )
        cls.agreement = cls._create_agreement(
            "L-109 Agreement",
            10.0,
            cls.degree_f | cls.degree_a,
        )
        cls.client_file = cls.env["qlk.client.file"].create(
            {
                "name": "L-109 Test Client File",
                "partner_id": cls.client.id,
                "service_profile_type": "litigation",
                "legal_service_type_ids": [(6, 0, cls.litigation_service.ids)],
                "allowed_litigation_degree_ids": [
                    (6, 0, (cls.degree_f | cls.degree_a).ids)
                ],
                "engagement_ids": [(6, 0, cls.agreement.ids)],
                "litigation_client_code": "L-109",
                "litigation_code_locked": True,
                "poa_status": "verified",
            }
        )
        cls.agreement.write(
            {
                "client_file_id": cls.client_file.id,
                "client_file_ids": [(4, cls.client_file.id)],
            }
        )
        project_values = cls.client_file._prepare_project_vals_from_engagement(
            cls.agreement
        )
        cls.projects = cls.Project
        for number in range(1, 4):
            cls.projects |= cls.Project.with_context(
                create_from_client_file=True
            ).create(dict(project_values, name="L-109 Project %s" % number))

    @classmethod
    def _create_agreement(cls, name, planned_hours, degrees):
        """Create a client-approved litigation agreement for the fixture."""
        return cls.env["bd.engagement.letter"].create(
            {
                "reference": name,
                "partner_id": cls.client.id,
                "contract_type": "hours",
                "service_type": "litigation",
                "approval_role": "manager",
                "state": "approved_client",
                "planned_hours": planned_hours,
                "legal_service_type_ids": [
                    (6, 0, cls.litigation_service.ids)
                ],
                "litigation_degree_ids": [(6, 0, degrees.ids)],
                "lawyer_ids": [(6, 0, cls.employee.ids)],
            }
        )

    def _create_case(self, project, degree, number):
        """Create a complete case record using a project-allowed degree."""
        return self.env["qlk.case"].create(
            {
                "name": "Test Case %s" % number,
                "name2": "Test Case %s" % number,
                "case_number": number,
                "case_year": "2026",
                "folder_number": number,
                "folder_year": "2026",
                "date": fields.Date.today(),
                "client_id": self.client.id,
                "opponent_id": self.opponent.id,
                "litigation_flow": "litigation",
                "employee_id": self.employee.id,
                "project_id": project.id,
                "litigation_degree_id": degree.id,
            }
        )

    def test_litigation_project_and_case_numbering(self):
        """Use client-file-local sequences and append degrees only to cases."""
        self.assertEqual(
            self.projects.mapped("service_code"),
            ["L-109/1", "L-109/2", "L-109/3"],
        )
        first_case = self._create_case(self.projects[0], self.degree_f, 1)
        second_case = self._create_case(self.projects[1], self.degree_a, 2)
        self.assertEqual(first_case.service_code, "L-109/1/F")
        self.assertEqual(second_case.service_code, "L-109/2/A")

    def test_disallowed_litigation_degree_is_rejected(self):
        """Reject degrees absent from the selected agreement."""
        with self.assertRaises(ValidationError):
            self._create_case(self.projects[0], self.degree_c, 3)

    def test_planned_and_manual_consumed_hours_are_audited(self):
        """Recompute remaining and overage values and retain manual evidence."""
        project = self.projects[0]
        with self.assertRaises(UserError):
            project.write({"manual_consumed_hours": 1.0})
        project.write({"planned_hours": 5.0})
        project._apply_manual_consumed_hours(7.0, "Court preparation adjustment")
        self.assertEqual(project.remaining_hours, -2.0)
        self.assertEqual(project.over_agreement_hours, 2.0)
        self.assertEqual(project.hour_audit_ids[:1].old_value, 0.0)
        self.assertEqual(project.hour_audit_ids[:1].new_value, 7.0)
        self.assertEqual(
            project.hour_audit_ids[:1].reason,
            "Court preparation adjustment",
        )
        self.assertTrue(
            project.hour_tracking_ids.filtered(
                lambda line: line.field_name == "planned_hours"
                and line.source == "manual"
            )
        )
        self.assertTrue(
            project.hour_tracking_ids.filtered(
                lambda line: line.field_name == "consumed_hours"
                and line.source == "manual"
            )
        )

    def test_new_project_requires_agreement(self):
        """Require an agreement for new projects while preserving legacy rows."""
        values = self.client_file._prepare_project_vals_from_engagement(
            self.agreement
        )
        values.pop("engagement_letter_id")
        with self.assertRaises(ValidationError):
            self.Project.with_context(create_from_client_file=True).create(values)

    def test_timesheet_create_modify_and_delete_refreshes_project(self):
        """Apply every timesheet mutation to the project in the same transaction."""
        project = self.projects[0]
        case = self._create_case(project, self.degree_f, 4)
        task = self.env["project.task"].create(
            {
                "name": "Timesheet Task",
                "case_id": case.id,
                "allocated_hours": 8.0,
            }
        )
        line = self.env["account.analytic.line"].create(
            {
                "name": "Draft pleading",
                "date": fields.Date.today(),
                "employee_id": self.employee.id,
                "project_id": task.project_id.id,
                "task_id": task.id,
                "unit_amount": 2.0,
            }
        )
        self.assertEqual(project.consumed_hours, 2.0)
        line.write({"unit_amount": 3.5})
        self.assertEqual(project.consumed_hours, 3.5)
        line.unlink()
        self.assertEqual(project.consumed_hours, 0.0)
        self.assertGreaterEqual(
            len(project.hour_tracking_ids.filtered(lambda item: item.source == "timesheet")),
            3,
        )

    def test_task_approval_and_rejection_refreshes_consumed_and_approved(self):
        """Separate accepted consumption from approved hours and rejected time."""
        project = self.projects[0]
        task = self.env["qlk.task"].create(
            {
                "name": "Approval Hours",
                "department": "management",
                "employee_id": self.employee.id,
                "project_id": project.id,
                "hours_spent": 2.0,
                "date_start": fields.Date.today(),
                "approval_state": "draft",
            }
        )
        self.assertEqual(project.consumed_hours, 2.0)
        self.assertEqual(project.approved_hours, 0.0)
        task.write({"approval_state": "approved"})
        self.assertEqual(project.consumed_hours, 2.0)
        self.assertEqual(project.approved_hours, 2.0)
        self.assertEqual(project.approved_hours_month, 2.0)
        task.write({"approval_state": "rejected"})
        self.assertEqual(project.consumed_hours, 0.0)
        self.assertEqual(project.approved_hours, 0.0)

    def test_agreement_reload_updates_project_and_allowed_degrees(self):
        """Reload agreement values only after the explicit confirmation action."""
        project = self.projects[2]
        replacement = self._create_agreement(
            "Replacement Agreement",
            20.0,
            self.degree_f,
        )
        replacement.write(
            {
                "client_file_id": self.client_file.id,
                "client_file_ids": [(4, self.client_file.id)],
            }
        )
        self.client_file.write({"engagement_ids": [(4, replacement.id)]})
        project._change_agreement(replacement, reload_information=True)
        self.assertEqual(project.engagement_letter_id, replacement)
        self.assertEqual(project.client_id, replacement.partner_id)
        self.assertEqual(project.planned_hours, 20.0)
        self.assertEqual(project.agreement_hours, 20.0)
        self.assertEqual(project.litigation_degree_ids, self.degree_f)
        self.assertTrue(
            project.hour_tracking_ids.filtered(
                lambda line: line.field_name == "planned_hours"
                and line.source == "agreement"
            )
        )

    def test_existing_non_litigation_records_remain_unchanged(self):
        """Confirm upgrades preserve legacy, Corporate, and Arbitration numbers."""
        legacy_projects = self.Project.browse(self.legacy_litigation_codes)
        self.assertEqual(
            {project.id: project.service_code for project in legacy_projects},
            self.legacy_litigation_codes,
        )
        for model_name in ("qlk.corporate.case", "qlk.arbitration.case"):
            records = self.env[model_name].with_context(active_test=False).search([])
            before = {record.id: record.service_code for record in records}
            records.invalidate_recordset(["service_code"])
            self.assertEqual(
                {record.id: record.service_code for record in records},
                before,
            )
