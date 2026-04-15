# -*- coding: utf-8 -*-
from datetime import datetime, time as dt_time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BDReportWizard(models.TransientModel):
    _name = "bd.report.wizard"
    _description = "BD Unified Report Wizard"

    date_from = fields.Date(
        string="Date From",
        required=True,
        default=lambda self: fields.Date.to_date(fields.Date.context_today(self)).replace(day=1),
    )
    date_to = fields.Date(
        string="Date To",
        required=True,
        default=fields.Date.context_today,
    )
    report_type = fields.Selection(
        [("xlsx", "Excel"), ("pdf", "PDF")],
        string="Report Type",
        default="xlsx",
        required=True,
    )
    record_type = fields.Selection(
        [
            ("proposal", "Proposals"),
            ("engagement", "Engagement Letters"),
            ("both", "Both"),
        ],
        string="Data",
        default="both",
        required=True,
    )

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise UserError(_("Date From must be earlier than or equal to Date To."))

    def _get_utc_datetime_bounds(self):
        self.ensure_one()
        timezone = pytz.timezone(self.env.user.tz or "UTC")
        start_local = timezone.localize(datetime.combine(self.date_from, dt_time.min))
        end_local = timezone.localize(datetime.combine(self.date_to, dt_time.max))
        start_utc = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
        end_utc = end_local.astimezone(pytz.UTC).replace(tzinfo=None)
        return fields.Datetime.to_string(start_utc), fields.Datetime.to_string(end_utc)

    def _get_model_domain(self, model_name):
        self.ensure_one()
        model = self.env[model_name]
        start_utc, end_utc = self._get_utc_datetime_bounds()
        create_date_domain = [
            "&",
            ("create_date", ">=", start_utc),
            ("create_date", "<=", end_utc),
        ]
        if "date" in model._fields and model._fields["date"].type == "date":
            document_date_domain = [
                "&",
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
            ]
            return ["|"] + create_date_domain + document_date_domain
        return create_date_domain

    def _get_records(self, data=None):
        self.ensure_one()
        data = data or {}
        Proposal = self.env["bd.proposal"].sudo()
        Engagement = self.env["bd.engagement.letter"].sudo()

        proposal_ids = data.get("proposals") or []
        engagement_ids = data.get("engagements") or []
        record_type = data.get("record_type") or self.record_type

        proposals = Proposal.browse(proposal_ids).exists() if proposal_ids else Proposal.browse()
        engagements = Engagement.browse(engagement_ids).exists() if engagement_ids else Engagement.browse()

        if not proposal_ids and record_type in ("proposal", "both"):
            proposals = Proposal.search(self._get_model_domain("bd.proposal"), order="code asc, name asc, id asc")
        if not engagement_ids and record_type in ("engagement", "both"):
            engagements = Engagement.search(
                self._get_model_domain("bd.engagement.letter"),
                order="code asc, reference asc, id asc",
            )

        if record_type == "proposal":
            engagements = Engagement.browse()
        elif record_type == "engagement":
            proposals = Proposal.browse()

        return proposals, engagements

    def _get_selection_label(self, record, field_name):
        field = record._fields.get(field_name)
        if not field or field.type != "selection":
            value = getattr(record, field_name, False)
            return value.display_name if getattr(value, "display_name", False) else (value or "")
        field_info = record.fields_get([field_name]).get(field_name, {})
        selection = dict(field_info.get("selection", []))
        value = getattr(record, field_name, False)
        return selection.get(value, "") if value else ""

    def _get_invoice(self, record):
        if "invoice_id" in record._fields and record.invoice_id:
            return record.invoice_id
        if "engagement_letter_id" in record._fields and record.engagement_letter_id and record.engagement_letter_id.invoice_id:
            return record.engagement_letter_id.invoice_id
        return self.env["account.move"]

    def _get_assigned_lawyer_name(self, record):
        if "lawyer_employee_id" in record._fields and record.lawyer_employee_id:
            return record.lawyer_employee_id.display_name
        if "lawyer_id" in record._fields and record.lawyer_id:
            return record.lawyer_id.display_name
        return ""

    def _prepare_row(self, record, row_type):
        invoice = self._get_invoice(record)
        total_legal_fees = record.total_legal_fees or 0.0
        paid_amount = max((invoice.amount_total or 0.0) - (invoice.amount_residual or 0.0), 0.0) if invoice else 0.0
        unpaid_amount = max(total_legal_fees - paid_amount, 0.0)
        currency = record.currency_id
        rounding = currency.rounding if currency else 0.01
        if currency.is_zero(unpaid_amount) if currency else abs(unpaid_amount) < rounding:
            payment_status = _("Paid")
            unpaid_amount = 0.0
        elif paid_amount:
            payment_status = _("Partial")
        else:
            payment_status = _("Not Paid")

        return {
            "type": row_type,
            "reference": record.code or getattr(record, "name", False) or getattr(record, "reference", False) or "",
            "client_name": record.partner_id.display_name if record.partner_id else "",
            "client_code": record.client_code or "",
            "service_type": self._get_selection_label(record, "retainer_type"),
            "contract_type": self._get_selection_label(record, "contract_type"),
            "billing_type": self._get_selection_label(record, "billing_type"),
            "assigned_lawyer": self._get_assigned_lawyer_name(record),
            "assignment_date": record.assigned_date or record.create_date,
            "total_legal_fees": total_legal_fees,
            "paid_amount": paid_amount,
            "unpaid_amount": unpaid_amount,
            "payment_status": payment_status,
            "currency_id": currency,
            "currency_name": currency.name or "",
            "currency_symbol": currency.symbol or currency.name or "",
        }

    def _group_totals_by_currency(self, rows):
        totals = {}
        for row in rows:
            currency_name = row["currency_name"] or _("N/A")
            entry = totals.setdefault(
                currency_name,
                {
                    "currency_name": currency_name,
                    "currency_symbol": row["currency_symbol"],
                    "fees": 0.0,
                    "paid": 0.0,
                    "unpaid": 0.0,
                },
            )
            entry["fees"] += row["total_legal_fees"]
            entry["paid"] += row["paid_amount"]
            entry["unpaid"] += row["unpaid_amount"]
        return [totals[key] for key in sorted(totals)]

    def _get_report_payload(self, data=None):
        self.ensure_one()
        data = data or {}
        proposals, engagements = self._get_records(data=data)
        proposal_rows = [self._prepare_row(record, "Proposal") for record in proposals]
        engagement_rows = [self._prepare_row(record, "Engagement") for record in engagements]

        return {
            "date_from": fields.Date.to_date(data.get("date_from")) if data.get("date_from") else self.date_from,
            "date_to": fields.Date.to_date(data.get("date_to")) if data.get("date_to") else self.date_to,
            "record_type": data.get("record_type") or self.record_type,
            "proposal_rows": proposal_rows,
            "engagement_rows": engagement_rows,
            "proposal_totals": self._group_totals_by_currency(proposal_rows),
            "engagement_totals": self._group_totals_by_currency(engagement_rows),
            "overall_totals": self._group_totals_by_currency(proposal_rows + engagement_rows),
        }

    @api.model
    def _get_report_payload_from_data(self, data=None):
        data = data or {}
        active_ids = self.env.context.get("active_ids") or []
        wizard = self.browse(active_ids[:1]).exists()
        if wizard:
            return wizard._get_report_payload(data=data)

        defaults = {
            "date_from": fields.Date.to_date(data.get("date_from")) if data.get("date_from") else fields.Date.context_today(self),
            "date_to": fields.Date.to_date(data.get("date_to")) if data.get("date_to") else fields.Date.context_today(self),
            "record_type": data.get("record_type") or "both",
            "report_type": data.get("report_type") or "xlsx",
        }
        virtual_wizard = self.new(defaults)
        return virtual_wizard._get_report_payload(data=data)

    def _prepare_report_action_data(self):
        self.ensure_one()
        proposals, engagements = self._get_records()
        if not proposals and not engagements:
            raise UserError(_("No BD records were found for the selected date range."))
        return {
            "proposals": proposals.ids,
            "engagements": engagements.ids,
            "date_from": fields.Date.to_string(self.date_from),
            "date_to": fields.Date.to_string(self.date_to),
            "record_type": self.record_type,
        }

    def action_print_report(self):
        self.ensure_one()
        data = self._prepare_report_action_data()
        xmlid = (
            "qlk_management.action_bd_report_xlsx_wizard"
            if self.report_type == "xlsx"
            else "qlk_management.action_bd_report_pdf_wizard"
        )
        return self.env.ref(xmlid).report_action(self, data=data)
