# -*- coding: utf-8 -*-
"""Agreement-to-project synchronization with explicit reload confirmation."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class QlkProjectAgreement(models.Model):
    """Keep a legal project aligned with its mandatory engagement agreement."""

    _inherit = "qlk.project"

    engagement_letter_id = fields.Many2one(
        string="Agreement",
        tracking=True,
    )

    def _agreement_client_file(self, agreement):
        """Return the agreement client file matching this project's service profile."""
        self.ensure_one()
        client_files = agreement.client_file_ids if "client_file_ids" in agreement._fields else self.env["qlk.client.file"]
        if not client_files and "client_file_id" in agreement._fields and agreement.client_file_id:
            client_files = agreement.client_file_id
        matching = client_files.filtered(
            lambda item: item.service_profile_type == (self.service_category or self.service_type)
        )
        return matching[:1] or client_files[:1]

    @api.model
    def _agreement_hour_value(self, agreement):
        """Resolve the first configured agreement-hour field in business priority."""
        return (
            agreement.planned_hours
            or agreement.agreed_hours
            or agreement.allocated_hours
            or agreement.estimated_hours
            or 0.0
        )

    def _prepare_agreement_reload_values(self, agreement):
        """Map all supported agreement data into the current legal project."""
        self.ensure_one()
        if not agreement:
            raise ValidationError(_("Select an Agreement."))
        client_file = self._agreement_client_file(agreement)
        if client_file and self.client_file_id and client_file != self.client_file_id:
            raise ValidationError(
                _(
                    "The selected Agreement belongs to another Client File. "
                    "Changing a project's legal file would invalidate existing legal numbering."
                )
            )
        if agreement.partner_id != self.client_id:
            raise ValidationError(_("The selected Agreement must belong to the project's Client."))

        services = (
            agreement._get_legal_service_type_ids_for_transfer()
            if hasattr(agreement, "_get_legal_service_type_ids_for_transfer")
            else agreement.legal_service_type_ids
        )
        if client_file:
            profile = client_file.service_profile_type
            services = services.filtered(
                lambda service: client_file._profile_from_service_code(service.code) == profile
            )
        degrees = (
            agreement._get_allowed_litigation_degree_ids_for_transfer()
            if hasattr(agreement, "_get_allowed_litigation_degree_ids_for_transfer")
            else agreement.litigation_degree_ids
        )
        responsible_users = agreement.lawyer_user_id | agreement.lawyer_ids.mapped("user_id") | agreement.reviewer_id
        planned_hours = self._agreement_hour_value(agreement)
        values = {
            "engagement_letter_id": agreement.id,
            "client_id": agreement.partner_id.id,
            "contract_type": agreement.contract_type,
            "billing_type": agreement.billing_type,
            "currency_id": agreement.currency_id.id,
            "lawyer_id": agreement.lawyer_employee_id.id,
            "contact_person_ids": [(6, 0, agreement.lawyer_ids.ids)],
            "responsible_user_ids": [(6, 0, responsible_users.ids)],
            "retainer_type": agreement.retainer_type,
            "agreed_hours": planned_hours,
            "planned_hours": planned_hours,
            "start_date": agreement.year_start_date or agreement.date,
            "end_date": agreement.year_end_date,
            "description": agreement.description or agreement.services_description,
            "scope_details": agreement.scope_of_work,
            "contract_terms": agreement.scope_of_work,
            "payment_terms": agreement.payment_terms,
            "notes": agreement.legal_note or agreement.contact_details,
            "phone": agreement.partner_id.phone or agreement.partner_id.mobile,
        }
        if client_file:
            values["client_file_id"] = client_file.id
        if services:
            values["legal_service_type_ids"] = [(6, 0, services.ids)]
            values["service_type"] = client_file.service_profile_type if client_file else agreement.service_type
        if self._allows_legal_service("litigation") or agreement.service_type in ("litigation", "pre_litigation"):
            if not degrees:
                raise ValidationError(
                    _("The selected litigation Agreement has no Allowed Litigation Degrees.")
                )
            values["litigation_degree_ids"] = [(6, 0, degrees.ids)]
            values["allowed_litigation_degree_ids"] = [(6, 0, degrees.ids)]
        return values

    def action_change_agreement(self):
        """Open the explicit Yes/No agreement reload confirmation wizard."""
        self.ensure_one()
        self._ensure_legal_manager()
        return {
            "type": "ir.actions.act_window",
            "name": _("Change Agreement"),
            "res_model": "qlk.project.agreement.reload.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
                "default_agreement_id": self.engagement_letter_id.id,
            },
        }

    def _change_agreement(self, agreement, reload_information):
        """Apply the selected agreement and optionally reload all mapped values."""
        self.ensure_one()
        self._ensure_legal_manager()
        if not agreement:
            raise ValidationError(_("Agreement is required."))
        if agreement.state != "approved_client":
            raise ValidationError(_("Only a client-approved Agreement can be selected."))
        if agreement.partner_id != self.client_id:
            raise ValidationError(_("The selected Agreement must belong to the project's Client."))
        agreement_client_file = self._agreement_client_file(agreement)
        if (
            agreement_client_file
            and self.client_file_id
            and agreement_client_file != self.client_file_id
        ):
            raise ValidationError(
                _("The selected Agreement must belong to the project's Client File.")
            )
        before = self._hour_snapshot()
        values = (
            self._prepare_agreement_reload_values(agreement)
            if reload_information
            else {"engagement_letter_id": agreement.id}
        )
        self.with_context(
            agreement_reload=True,
            hour_change_source="agreement",
            skip_hour_tracking=True,
        ).write(values)
        self._track_hour_changes(before, "agreement")
        self.message_post(
            body=(
                _("Agreement changed to %(agreement)s and project information was reloaded.")
                if reload_information
                else _("Agreement changed to %(agreement)s without reloading project information.")
            )
            % {"agreement": agreement.display_name}
        )
        return True


class QlkProjectAgreementRules(models.Model):
    """Enforce agreement-derived litigation degree boundaries."""

    _inherit = "qlk.project"

    @api.constrains("engagement_letter_id", "litigation_degree_ids")
    def _check_agreement_litigation_degrees(self):
        """Reject project degrees that do not exist on the selected agreement."""
        for project in self:
            agreement = project.engagement_letter_id
            if not agreement or not project._allows_legal_service("litigation"):
                continue
            allowed = agreement.litigation_degree_ids
            if not allowed:
                raise ValidationError(_("The litigation Agreement must define Allowed Litigation Degrees."))
            if project.litigation_degree_ids - allowed:
                raise ValidationError(
                    _("Project litigation degrees must be limited to the selected Agreement's Allowed Degrees.")
                )
