import json
import logging

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrBiometricDevice(models.Model):
    _name = "hr.biometric.device"
    _description = "Biometric Attendance Device"

    name = fields.Char(required=True)
    base_url = fields.Char(required=True, help="Biometric API base URL")
    endpoint_path = fields.Char(default="/logs", required=True)
    api_key = fields.Char(string="API Key")
    request_timeout = fields.Integer(default=20)
    verify_ssl = fields.Boolean(default=True)
    last_sync_at = fields.Datetime(copy=False)
    active = fields.Boolean(default=True)

    def _fetch_remote_logs(self):
        self.ensure_one()
        url = f"{(self.base_url or '').rstrip('/')}/{(self.endpoint_path or '').lstrip('/')}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        params = {}
        if self.last_sync_at:
            params["since"] = fields.Datetime.to_string(self.last_sync_at)

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=self.request_timeout,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("logs", "data", "items", "results"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        return []

    def _normalize_event_type(self, value):
        text = (value or "").strip().lower()
        if text in ("check_out", "checkout", "out", "clock_out", "sign_out"):
            return "check_out"
        return "check_in"

    def _resolve_employee(self, user_code):
        if not user_code:
            return self.env["hr.employee"]
        employee = self.env["hr.employee"].search([("biometric_user_code", "=", user_code)], limit=1)
        if employee:
            return employee
        return self.env["hr.employee"].search([("barcode", "=", user_code)], limit=1)

    def _apply_attendance_event(self, employee, event_type, event_dt):
        Attendance = self.env["hr.attendance"].sudo()
        open_attendance = Attendance.search(
            [
                ("employee_id", "=", employee.id),
                ("check_out", "=", False),
            ],
            order="check_in desc",
            limit=1,
        )

        if event_type == "check_out":
            if open_attendance and event_dt >= open_attendance.check_in:
                open_attendance.write({"check_out": event_dt, "out_mode": "technical"})
                return open_attendance, "processed", "Checkout matched with open attendance"
            attendance = Attendance.create(
                {
                    "employee_id": employee.id,
                    "check_in": event_dt,
                    "check_out": event_dt,
                    "in_mode": "technical",
                    "out_mode": "technical",
                }
            )
            return attendance, "processed", "Checkout created as standalone record"

        # event_type == check_in
        if open_attendance:
            delta_seconds = abs((event_dt - open_attendance.check_in).total_seconds())
            if delta_seconds <= 60:
                return open_attendance, "skipped", "Duplicate check-in ignored"
            if event_dt > open_attendance.check_in:
                open_attendance.write({"check_out": event_dt, "out_mode": "technical"})
                return open_attendance, "processed", "Open attendance auto-closed by new check-in"

        attendance = Attendance.create(
            {
                "employee_id": employee.id,
                "check_in": event_dt,
                "in_mode": "technical",
            }
        )
        return attendance, "processed", "Check-in created"

    def _process_single_log(self, item):
        self.ensure_one()
        user_code = str(item.get("user_code") or item.get("employee_code") or item.get("user_id") or "").strip()
        raw_type = item.get("event_type") or item.get("type") or item.get("action")
        event_type = self._normalize_event_type(raw_type)
        event_dt = fields.Datetime.to_datetime(item.get("timestamp") or item.get("event_time") or item.get("datetime"))
        if not event_dt:
            event_dt = fields.Datetime.now()

        external_log_id = str(
            item.get("external_id")
            or item.get("log_id")
            or item.get("id")
            or f"{user_code}-{fields.Datetime.to_string(event_dt)}-{event_type}"
        )

        Log = self.env["hr.biometric.log"].sudo()
        if Log.search_count([("device_id", "=", self.id), ("external_log_id", "=", external_log_id)]):
            return

        employee = self._resolve_employee(user_code)
        if not employee:
            Log.create(
                {
                    "device_id": self.id,
                    "external_log_id": external_log_id,
                    "event_type": event_type,
                    "event_datetime": event_dt,
                    "status": "unmapped",
                    "message": f"No employee mapped for user code: {user_code}",
                    "payload_json": json.dumps(item, ensure_ascii=False, default=str),
                }
            )
            return

        try:
            attendance, status, message = self._apply_attendance_event(employee, event_type, event_dt)
            Log.create(
                {
                    "device_id": self.id,
                    "external_log_id": external_log_id,
                    "employee_id": employee.id,
                    "event_type": event_type,
                    "event_datetime": event_dt,
                    "attendance_id": attendance.id if attendance else False,
                    "status": status,
                    "message": message,
                    "payload_json": json.dumps(item, ensure_ascii=False, default=str),
                }
            )
        except Exception as error:
            Log.create(
                {
                    "device_id": self.id,
                    "external_log_id": external_log_id,
                    "employee_id": employee.id,
                    "event_type": event_type,
                    "event_datetime": event_dt,
                    "status": "error",
                    "message": str(error),
                    "payload_json": json.dumps(item, ensure_ascii=False, default=str),
                }
            )

    def action_sync_attendance(self):
        for device in self:
            try:
                logs = device._fetch_remote_logs()
                for item in logs:
                    if isinstance(item, dict):
                        device._process_single_log(item)
                device.last_sync_at = fields.Datetime.now()
            except Exception as error:
                _logger.exception("Biometric sync failed for device %s: %s", device.name, error)

    @api.model
    def cron_sync_all_devices(self):
        devices = self.search([("active", "=", True)])
        devices.action_sync_attendance()


class HrBiometricLog(models.Model):
    _name = "hr.biometric.log"
    _description = "Biometric Log"
    _order = "event_datetime desc, id desc"

    device_id = fields.Many2one("hr.biometric.device", required=True, ondelete="cascade")
    external_log_id = fields.Char(required=True, index=True)
    employee_id = fields.Many2one("hr.employee", ondelete="set null")
    event_type = fields.Selection(
        [("check_in", "Check In"), ("check_out", "Check Out")],
        required=True,
    )
    event_datetime = fields.Datetime(required=True)
    attendance_id = fields.Many2one("hr.attendance", ondelete="set null")
    status = fields.Selection(
        [
            ("processed", "Processed"),
            ("skipped", "Skipped"),
            ("unmapped", "Unmapped"),
            ("error", "Error"),
        ],
        default="processed",
        required=True,
    )
    message = fields.Char()
    payload_json = fields.Text()

    _sql_constraints = [
        (
            "hr_biometric_log_unique_external",
            "unique(device_id, external_log_id)",
            "Each external biometric log must be imported only once per device.",
        )
    ]
