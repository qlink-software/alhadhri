from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCorporateHoursLock(TransactionCase):
    def test_locked_record_rejects_every_protected_field(self):
        protected_fields = self.env["qlk.corporate.case"]._LOCKED_HOUR_FIELDS
        for field_name in protected_fields:
            corporate_case = self.env["qlk.corporate.case"].new({"lock_hours": True})
            with self.assertRaisesRegex(
                ValidationError,
                "Agreement Hours are locked and cannot be modified.",
            ):
                corporate_case.write({field_name: 1.0})

    def test_unlocked_record_allows_normal_field_validation(self):
        corporate_case = self.env["qlk.corporate.case"].new({"lock_hours": False})
        self.assertTrue(corporate_case._ensure_hours_unlocked({"planned_hours": 1.0}))

    def test_locked_record_allows_unrelated_updates(self):
        corporate_case = self.env["qlk.corporate.case"].new({"lock_hours": True})
        self.assertTrue(corporate_case._ensure_hours_unlocked({"notes": "Unrelated change"}))

    def test_lock_and_hours_cannot_be_changed_in_same_request(self):
        corporate_case = self.env["qlk.corporate.case"].new({"lock_hours": False})
        with self.assertRaises(ValidationError):
            corporate_case.write({"lock_hours": True, "planned_hours": 4.0})
