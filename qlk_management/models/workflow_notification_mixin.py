# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class QlkWorkflowNotificationMixin(models.AbstractModel):
    _name = "qlk.workflow.notification.mixin"
    _description = "QLK Workflow Email Notification Engine"

    workflow_notification_keys = fields.Text(
        string="Workflow Email Keys",
        copy=False,
        readonly=True,
        help="Technical idempotency keys used to prevent duplicate workflow emails.",
    )

    def _qlk_record_url(self):
        self.ensure_one()
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        ).rstrip("/")
        return "%s/web#id=%s&model=%s&view_type=form" % (base_url, self.id, self._name)

    def qlk_record_url(self):
        return self._qlk_record_url()

    def _qlk_document_name(self):
        self.ensure_one()
        if "name" in self._fields and self.name:
            return self.name
        if "code" in self._fields and self.code:
            return self.code
        return self.display_name

    def qlk_document_name(self):
        return self._qlk_document_name()

    def _qlk_responsible_lawyer_name(self):
        self.ensure_one()
        if "lawyer_id" in self._fields and self.lawyer_id:
            return self.lawyer_id.name
        if "lawyer_employee_id" in self._fields and self.lawyer_employee_id:
            return self.lawyer_employee_id.name
        if "lawyer_user_ids" in self._fields and self.lawyer_user_ids:
            return ", ".join(self.lawyer_user_ids.mapped("name"))
        return "-"

    def qlk_responsible_lawyer_name(self):
        return self._qlk_responsible_lawyer_name()

    def _qlk_notification_key_set(self):
        self.ensure_one()
        return set((self.workflow_notification_keys or "").splitlines())

    def _qlk_has_notification_key(self, key):
        self.ensure_one()
        return key in self._qlk_notification_key_set()

    def _qlk_mark_notification_key(self, key):
        self.ensure_one()
        keys = self._qlk_notification_key_set()
        keys.add(key)
        # نحفظ مفتاح الإرسال بعد نجاح البريد فقط حتى لا تتكرر الرسائل لنفس المرحلة.
        self.with_context(mail_notrack=True).sudo().write(
            {"workflow_notification_keys": "\n".join(sorted(keys))}
        )

    def _qlk_send_template_notification(self, template_xmlid, email_to, key, label):
        if not template_xmlid:
            _logger.error("Workflow email template is not configured for %s", self._name)
            return False
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            _logger.error("Missing workflow mail template: %s", template_xmlid)
            for record in self:
                record.message_post(
                    body=_("Workflow email was not sent because template %s was not found.")
                    % template_xmlid
                )
            return False

        sent = False
        for record in self:
            if not email_to:
                _logger.warning("Workflow email skipped for %s/%s: no recipient", record._name, record.id)
                continue
            if record._qlk_has_notification_key(key):
                _logger.info(
                    "Duplicate workflow email skipped for %s/%s with key %s",
                    record._name,
                    record.id,
                    key,
                )
                continue
            try:
                company = (
                    record.company_id
                    if "company_id" in record._fields and record.company_id
                    else self.env.company
                )
                template.sudo().with_company(company).send_mail(
                    record.id,
                    force_send=True,
                    raise_exception=True,
                    email_values={"email_to": email_to},
                )
                record._qlk_mark_notification_key(key)
                record.message_post(
                    body=_("Workflow email sent: %(label)s to %(email)s")
                    % {"label": label, "email": email_to}
                )
                sent = True
            except Exception:
                _logger.exception(
                    "Failed to send workflow email %s for %s/%s",
                    template_xmlid,
                    record._name,
                    record.id,
                )
                record.message_post(
                    body=_("Workflow email failed: %(label)s to %(email)s")
                    % {"label": label, "email": email_to}
                )
        return sent

    def _qlk_approval_recipient(self):
        self.ensure_one()
        return {
            "manager": "a.alhadhri@alhadhrilawfirm.com",
            "assistant_manager": "m.alhadhri@alhadhrilawfirm.com",
        }.get(self.approval_role)

    def _qlk_approval_template_xmlid(self):
        self.ensure_one()
        template_map = {
            "bd.proposal": {
                "manager": "qlk_management.mail_template_proposal_manager_approval_request",
                "assistant_manager": "qlk_management.mail_template_proposal_assistant_manager_approval_request",
            },
            "bd.engagement.letter": {
                "manager": "qlk_management.mail_template_engagement_manager_approval_request",
                "assistant_manager": "qlk_management.mail_template_engagement_assistant_manager_approval_request",
            },
        }
        return template_map.get(self._name, {}).get(self.approval_role)

    def _qlk_send_approval_request_email(self):
        for record in self:
            template_xmlid = record._qlk_approval_template_xmlid()
            email_to = record._qlk_approval_recipient()
            key = "approval_request:%s" % (record.approval_role or "unknown")
            record._qlk_send_template_notification(
                template_xmlid,
                email_to,
                key,
                _("Approval request"),
            )

    def _qlk_monitor_template_xmlid(self, event):
        self.ensure_one()
        template_map = {
            "bd.proposal": {
                "manager_approved": "qlk_management.mail_template_proposal_monitor_approved",
                "assistant_manager_approved": "qlk_management.mail_template_proposal_monitor_approved",
                "sent_to_client": "qlk_management.mail_template_proposal_monitor_sent_to_client",
                "client_approved": "qlk_management.mail_template_proposal_monitor_client_approved",
                "client_rejected": "qlk_management.mail_template_proposal_monitor_client_rejected",
            },
            "bd.engagement.letter": {
                "manager_approved": "qlk_management.mail_template_engagement_monitor_approved",
                "assistant_manager_approved": "qlk_management.mail_template_engagement_monitor_approved",
                "sent_to_client": "qlk_management.mail_template_engagement_monitor_sent_to_client",
                "client_approved": "qlk_management.mail_template_engagement_monitor_client_approved",
                "client_rejected": "qlk_management.mail_template_engagement_monitor_client_rejected",
            },
        }
        return template_map.get(self._name, {}).get(event)

    def _qlk_send_monitoring_email(self, event):
        labels = {
            "manager_approved": _("Manager approved"),
            "assistant_manager_approved": _("Assistant manager approved"),
            "sent_to_client": _("Sent to client"),
            "client_approved": _("Client approved"),
            "client_rejected": _("Client rejected"),
        }
        for record in self:
            record._qlk_send_template_notification(
                record._qlk_monitor_template_xmlid(event),
                "dev@alhadhrilawfirm.com",
                "monitor:%s" % event,
                labels.get(event, event),
            )

    def _qlk_send_client_file_created_email(self):
        self._qlk_send_template_notification(
            "qlk_management.mail_template_client_file_created_poa_required",
            "mp.office@alhadhrilawfirm.com",
            "client_file_created_poa_required",
            _("New client file created"),
        )
