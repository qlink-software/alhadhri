# -*- coding: utf-8 -*-
import hashlib
import json
import logging
from datetime import datetime

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class QlkBiometricDevice(models.Model):
    _name = "qlk.biometric.device"
    _description = "Biometric Attendance Device"

    # هذا الحقل لاسم جهاز البصمة المستخدم في شاشة الإعدادات.
    name = fields.Char(required=True)
    # هذا الحقل لتفعيل/إيقاف الجهاز من المزامنة الدورية.
    active = fields.Boolean(default=True)
    # هذا الحقل يحفظ رابط واجهة API الخاص بالجهاز.
    endpoint_url = fields.Char(string="Endpoint URL", required=True)
    # هذا الحقل لتخزين رمز الوصول إن كان الجهاز يتطلب Authentication.
    api_token = fields.Char(string="API Token")
    # هذا الحقل يحدد مهلة الاتصال بالثواني لتفادي تجميد الكرون.
    request_timeout = fields.Integer(string="Request Timeout (sec)", default=20)
    # هذا الحقل يحدد التحقق من SSL عند الاتصال بالجهاز.
    verify_ssl = fields.Boolean(string="Verify SSL", default=True)
    # هذا الحقل يحفظ آخر وقت مزامنة ناجحة للأحداث.
    last_sync_at = fields.Datetime(string="Last Sync At", readonly=True, copy=False)
    # هذا الربط يعرض خرائط المستخدمين المرتبطة بالجهاز.
    user_map_ids = fields.One2many("qlk.biometric.user.map", "device_id", string="User Mapping")
    # هذا الربط يعرض سجل أحداث البصمة التي تمت مزامنتها.
    log_ids = fields.One2many("qlk.biometric.log", "device_id", string="Synced Logs")

    # ------------------------------------------------------------------------------
    # هذه الدالة تبني Headers للاتصال الخارجي مع دعم Bearer Token عند وجوده.
    # ------------------------------------------------------------------------------
    def _build_request_headers(self):
        self.ensure_one()
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = "Bearer %s" % self.api_token
        return headers

    # ------------------------------------------------------------------------------
    # هذه الدالة تستخرج قائمة الأحداث من أي تنسيق JSON شائع (list أو dict).
    # ------------------------------------------------------------------------------
    def _extract_events_payload(self, payload):
        self.ensure_one()
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("events", "data", "results", "records", "logs"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    # ------------------------------------------------------------------------------
    # هذه الدالة تحوّل الوقت القادم من الجهاز إلى Datetime صالح في أودو.
    # ------------------------------------------------------------------------------
    def _parse_event_datetime(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            return fields.Datetime.to_string(value)
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(normalized)
                return fields.Datetime.to_string(parsed)
            except ValueError:
                try:
                    parsed = fields.Datetime.to_datetime(value)
                    return fields.Datetime.to_string(parsed)
                except Exception:
                    return False
        return False

    # ------------------------------------------------------------------------------
    # هذه الدالة توحّد شكل حدث البصمة إلى قالب ثابت قبل المعالجة.
    # ------------------------------------------------------------------------------
    def _normalize_event(self, raw_event):
        self.ensure_one()
        if not isinstance(raw_event, dict):
            return False

        user_code = (
            raw_event.get("user_code")
            or raw_event.get("user_id")
            or raw_event.get("pin")
            or raw_event.get("employee_code")
        )
        if user_code is None:
            return False
        user_code = str(user_code).strip()
        if not user_code:
            return False

        event_dt = self._parse_event_datetime(
            raw_event.get("event_time")
            or raw_event.get("timestamp")
            or raw_event.get("punch_time")
            or raw_event.get("datetime")
        )
        if not event_dt:
            return False

        raw_type = (
            str(
                raw_event.get("event_type")
                or raw_event.get("punch_type")
                or raw_event.get("status")
                or raw_event.get("type")
                or "check_in"
            )
            .strip()
            .lower()
        )
        if raw_type in ("in", "checkin", "check_in", "0", "entry"):
            event_type = "check_in"
        elif raw_type in ("out", "checkout", "check_out", "1", "exit"):
            event_type = "check_out"
        else:
            event_type = "check_in"

        external_ref = (
            raw_event.get("external_ref")
            or raw_event.get("transaction_id")
            or raw_event.get("log_id")
            or raw_event.get("id")
        )
        if external_ref is None:
            hash_source = "%s|%s|%s|%s" % (self.id, user_code, event_dt, event_type)
            external_ref = hashlib.sha1(hash_source.encode("utf-8")).hexdigest()
        external_ref = str(external_ref)

        return {
            "device_user_code": user_code,
            "event_time": event_dt,
            "event_type": event_type,
            "external_ref": external_ref,
            "raw_payload": raw_event,
        }

    # ------------------------------------------------------------------------------
    # هذه الدالة تربط مستخدم جهاز البصمة بموظف Odoo عبر جدول الربط أو barcode.
    # ------------------------------------------------------------------------------
    def _resolve_employee(self, device_user_code):
        self.ensure_one()
        mapping = self.env["qlk.biometric.user.map"].search(
            [
                ("device_id", "=", self.id),
                ("device_user_code", "=", device_user_code),
                ("active", "=", True),
            ],
            limit=1,
        )
        if mapping.employee_id:
            return mapping.employee_id

        employee_model = self.env["hr.employee"].sudo()
        if "barcode" in employee_model._fields:
            employee = employee_model.search([("barcode", "=", device_user_code)], limit=1)
            if employee:
                return employee
        if "employee_code" in employee_model._fields:
            employee = employee_model.search([("employee_code", "=", device_user_code)], limit=1)
            if employee:
                return employee
        return self.env["hr.employee"]

    # ------------------------------------------------------------------------------
    # هذه الدالة تطبق حدث البصمة (دخول/خروج) على hr.attendance بشكل آمن.
    # ------------------------------------------------------------------------------
    def _apply_attendance_event(self, employee, event_time, event_type):
        self.ensure_one()
        attendance_model = self.env["hr.attendance"].sudo()
        event_dt = fields.Datetime.to_datetime(event_time)

        open_attendance = attendance_model.search(
            [("employee_id", "=", employee.id), ("check_out", "=", False)],
            order="check_in desc",
            limit=1,
        )

        if event_type == "check_in":
            if open_attendance and open_attendance.check_in and open_attendance.check_in <= event_dt:
                return "duplicate"
            attendance_model.create(
                {
                    "employee_id": employee.id,
                    "check_in": event_time,
                }
            )
            return "processed"

        if open_attendance:
            if open_attendance.check_in and event_dt < open_attendance.check_in:
                return "duplicate"
            open_attendance.write({"check_out": event_time})
            return "processed"

        # في حال وصول checkout بدون checkin مفتوح ننشئ سجل متوازن لتفادي فقدان الأثر.
        attendance_model.create(
            {
                "employee_id": employee.id,
                "check_in": event_time,
                "check_out": event_time,
            }
        )
        return "processed"

    # ------------------------------------------------------------------------------
    # هذه الدالة تنفذ مزامنة جهاز واحد من الـ API إلى hr.attendance.
    # ------------------------------------------------------------------------------
    def action_sync_now(self):
        for device in self:
            device._sync_device_events()
        return True

    # ------------------------------------------------------------------------------
    # هذا المنطق يجلب أحداث الجهاز ويخزنها ويطبقها على الحضور.
    # ------------------------------------------------------------------------------
    def _sync_device_events(self):
        self.ensure_one()

        params = {}
        if self.last_sync_at:
            params["from"] = fields.Datetime.to_string(self.last_sync_at)

        try:
            response = requests.get(
                self.endpoint_url,
                headers=self._build_request_headers(),
                params=params,
                timeout=max(self.request_timeout, 5),
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            _logger.exception("Biometric sync failed for device %s", self.display_name)
            self.message_post(body=_("Biometric sync failed: %s") % error)
            return False

        events = self._extract_events_payload(payload)
        log_model = self.env["qlk.biometric.log"].sudo()

        for raw_event in events:
            normalized = self._normalize_event(raw_event)
            if not normalized:
                continue

            exists = log_model.search(
                [
                    ("device_id", "=", self.id),
                    ("external_ref", "=", normalized["external_ref"]),
                ],
                limit=1,
            )
            if exists:
                continue

            employee = self._resolve_employee(normalized["device_user_code"])
            status = "unmapped"
            note = ""
            if employee:
                try:
                    status = self._apply_attendance_event(
                        employee,
                        normalized["event_time"],
                        normalized["event_type"],
                    )
                except Exception as error:
                    status = "error"
                    note = str(error)

            log_model.create(
                {
                    "device_id": self.id,
                    "employee_id": employee.id if employee else False,
                    "device_user_code": normalized["device_user_code"],
                    "event_time": normalized["event_time"],
                    "event_type": normalized["event_type"],
                    "external_ref": normalized["external_ref"],
                    "status": status,
                    "note": note,
                    "raw_payload": json.dumps(normalized["raw_payload"], ensure_ascii=False),
                }
            )

        self.last_sync_at = fields.Datetime.now()
        return True

    # ------------------------------------------------------------------------------
    # هذا الكرون لمزامنة كل أجهزة البصمة النشطة بشكل دوري.
    # ------------------------------------------------------------------------------
    @api.model
    def cron_sync_biometric_attendance(self):
        devices = self.search([("active", "=", True)])
        for device in devices:
            device._sync_device_events()
        return True


class QlkBiometricUserMap(models.Model):
    _name = "qlk.biometric.user.map"
    _description = "Biometric Device User Mapping"

    # هذا الربط يحدد الجهاز المرتبط بالمستخدم الخارجي.
    device_id = fields.Many2one("qlk.biometric.device", required=True, ondelete="cascade")
    # هذا الحقل هو كود المستخدم كما يأتي من جهاز البصمة.
    device_user_code = fields.Char(required=True)
    # هذا الربط يحدد الموظف الذي يستقبل سجلات هذا المستخدم الخارجي.
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    # هذا الحقل يسمح بتجميد الربط بدون الحذف.
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "qlk_biometric_user_map_unique",
            "unique(device_id, device_user_code)",
            "Device user code must be unique per biometric device.",
        )
    ]


class QlkBiometricLog(models.Model):
    _name = "qlk.biometric.log"
    _description = "Biometric Attendance Sync Log"
    _order = "event_time desc, id desc"

    # هذا الربط للجهاز الذي أرسل الحدث.
    device_id = fields.Many2one("qlk.biometric.device", required=True, ondelete="cascade", index=True)
    # هذا الربط للموظف الذي تم ربط الحدث به.
    employee_id = fields.Many2one("hr.employee", ondelete="set null", index=True)
    # هذا الحقل يحفظ كود المستخدم الخارجي القادم من الجهاز.
    device_user_code = fields.Char(required=True, index=True)
    # هذا الحقل وقت الحدث الفعلي القادم من جهاز البصمة.
    event_time = fields.Datetime(required=True, index=True)
    # هذا الحقل يحدد نوع الحركة (دخول / خروج).
    event_type = fields.Selection(
        [("check_in", "Check-In"), ("check_out", "Check-Out")],
        required=True,
        default="check_in",
    )
    # هذا الحقل معرف خارجي لمنع معالجة نفس السجل مرتين.
    external_ref = fields.Char(required=True, index=True)
    # هذا الحقل يوضح نتيجة المعالجة لأغراض المتابعة.
    status = fields.Selection(
        [
            ("processed", "Processed"),
            ("duplicate", "Duplicate"),
            ("unmapped", "Unmapped User"),
            ("error", "Error"),
        ],
        default="processed",
        required=True,
        index=True,
    )
    # هذا الحقل لتسجيل ملاحظة الخطأ عند فشل المعالجة.
    note = fields.Char()
    # هذا الحقل يخزن الـ payload الخام القادم من الجهاز للتدقيق.
    raw_payload = fields.Text()

    _sql_constraints = [
        (
            "qlk_biometric_log_unique_ref",
            "unique(device_id, external_ref)",
            "This biometric event has already been synchronized.",
        )
    ]
