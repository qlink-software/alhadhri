# -*- coding: utf-8 -*-
import re

from odoo import _, api, models
from odoo.exceptions import ValidationError


LEGAL_SERVICE_PREFIXES = {
    "litigation": "L",
    "pre_litigation": "L",
    "corporate": "C",
    "arbitration": "A",
}

LEGAL_CLIENT_CODE_FIELDS = {
    "litigation": ("litigation_client_code", "litigation_client_sequence"),
    "pre_litigation": ("litigation_client_code", "litigation_client_sequence"),
    "corporate": ("corporate_client_code", "corporate_client_sequence"),
    "arbitration": ("arbitration_client_code", "arbitration_client_sequence"),
}

CLIENT_SEQUENCE_CODES = {
    "litigation": "qlk.client.file.litigation",
    "corporate": "qlk.client.file.corporate",
    "arbitration": "qlk.client.file.arbitration",
}


class QlkLegalNumberingEngine(models.AbstractModel):
    _name = "qlk.legal.numbering.engine"
    _description = "Reusable Legal Numbering Engine"

    @api.model
    def _ensure_client_file_profile_columns(self):
        cr = self.env.cr
        cr.execute("SELECT to_regclass('qlk_client_file')")
        if not cr.fetchone()[0]:
            return False
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS litigation_client_code varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS corporate_client_code varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS arbitration_client_code varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS litigation_code_locked boolean DEFAULT false")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS corporate_code_locked boolean DEFAULT false")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS arbitration_code_locked boolean DEFAULT false")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS service_profile_type varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS client_profile_code varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS litigation_client_sequence integer DEFAULT 0")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS corporate_client_sequence integer DEFAULT 0")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS arbitration_client_sequence integer DEFAULT 0")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS litigation_project_next_number integer DEFAULT 1")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS corporate_project_next_number integer DEFAULT 1")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS arbitration_project_next_number integer DEFAULT 1")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_required boolean DEFAULT true")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_status varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_request_date date")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_received_date date")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_expiry_date date")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_notes text")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_uploaded_by integer")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_verified_by integer")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS poa_last_alert_date date")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS contract_type varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS billing_type varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS start_date date")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS end_date date")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS contact_details text")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS scope_of_work text")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS notes text")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS planned_hours double precision DEFAULT 0")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS consumed_hours double precision DEFAULT 0")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS remaining_hours double precision DEFAULT 0")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS hours_state varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS litigation_next_number integer DEFAULT 1")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS pre_litigation_next_number integer DEFAULT 1")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS arbitration_next_number integer DEFAULT 1")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS corporate_next_number integer DEFAULT 1")
        cr.execute(
            """
            UPDATE qlk_client_file
               SET litigation_client_sequence = COALESCE(litigation_client_sequence, 0),
                   corporate_client_sequence = COALESCE(corporate_client_sequence, 0),
                   arbitration_client_sequence = COALESCE(arbitration_client_sequence, 0),
                   litigation_code_locked = COALESCE(litigation_code_locked, false),
                   corporate_code_locked = COALESCE(corporate_code_locked, false),
                   arbitration_code_locked = COALESCE(arbitration_code_locked, false),
                   litigation_project_next_number = COALESCE(litigation_project_next_number, 1),
                   corporate_project_next_number = COALESCE(corporate_project_next_number, 1),
                   arbitration_project_next_number = COALESCE(arbitration_project_next_number, 1),
                   poa_required = COALESCE(poa_required, true),
                   poa_status = COALESCE(poa_status, 'draft'),
                   planned_hours = COALESCE(planned_hours, 0),
                   consumed_hours = COALESCE(consumed_hours, 0),
                   remaining_hours = COALESCE(remaining_hours, 0),
                   litigation_next_number = COALESCE(litigation_next_number, 1),
                   pre_litigation_next_number = COALESCE(pre_litigation_next_number, 1),
                   arbitration_next_number = COALESCE(arbitration_next_number, 1),
                   corporate_next_number = COALESCE(corporate_next_number, 1),
                   service_profile_type = COALESCE(service_profile_type, 'litigation')
            """
        )
        return True

    @api.model
    def _service_category(self, service_code):
        return "litigation" if service_code in ("litigation", "pre_litigation") else service_code

    @api.model
    def _lock(self, *parts):
        key = "qlk_legal_numbering:%s" % ":".join(str(part or "_") for part in parts)
        self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [key])

    @api.model
    def _parse_client_sequence(self, code):
        match = re.search(r"([A-Z])-?0*([0-9]+)$", code or "")
        return int(match.group(2)) if match else 0

    @api.model
    def _format_client_code(self, prefix, sequence):
        return "%s-%03d" % (prefix, int(sequence or 0))

    @api.model
    def _normalize_client_code(self, code, prefix):
        match = re.search(r"([A-Z])-?0*([0-9]+)$", code or "")
        if not match or match.group(1) != prefix:
            return code
        return self._format_client_code(prefix, match.group(2))

    @api.model
    def _parse_project_sequence(self, code):
        parts = (code or "").split("/")
        return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

    @api.model
    def _parse_record_sequence(self, code):
        parts = (code or "").split("/")
        return int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

    @api.model
    def _get_next_available_sequence(self, model_name, sequence_field, domain, parser=None, code_field="service_code"):
        records = self.env[model_name].sudo().with_context(active_test=False).search(domain)
        used = set()
        for record in records:
            number = record[sequence_field] if sequence_field in record._fields else 0
            if not number and parser and code_field in record._fields:
                number = parser(record[code_field])
            if number and number > 0:
                used.add(int(number))
        sequence = 1
        while sequence in used:
            sequence += 1
        return sequence

    @api.model
    def _generate_client_legal_code(self, client_file, service_code):
        client_file.ensure_one()
        category = self._service_category(service_code)
        field_name, sequence_field = LEGAL_CLIENT_CODE_FIELDS.get(category, (False, False))
        prefix = LEGAL_SERVICE_PREFIXES.get(category)
        if not field_name or not prefix:
            raise ValidationError(_("Unsupported legal service type for client numbering."))
        if client_file[field_name]:
            return client_file[field_name]

        company = client_file.company_id or self.env.company
        self._lock("client", company.id, category)
        client_file.invalidate_recordset([field_name, sequence_field])
        if client_file[field_name]:
            return client_file[field_name]
        sequence_code = CLIENT_SEQUENCE_CODES.get(category)
        code = self.env["ir.sequence"].sudo().with_company(company).next_by_code(sequence_code) if sequence_code else False
        if code:
            sequence = self._parse_client_sequence(code)
            code = self._format_client_code(prefix, sequence)
        else:
            sequence = 1
            code = self._format_client_code(prefix, sequence)
        client_file.sudo().with_context(mail_notrack=True, skip_client_code_lock=True).write({field_name: code, sequence_field: sequence})
        return code

    @api.model
    def _generate_project_code(self, project):
        """Generate a client-file-local project number under a transaction lock."""
        project.ensure_one()
        if not project.client_file_id:
            raise ValidationError(_("Cannot generate project code without a client file."))
        category = self._service_category(project._primary_service_code())
        client_code = self._generate_client_legal_code(project.client_file_id, category)
        company = project.company_id or project.client_file_id.company_id or self.env.company
        code_field = LEGAL_CLIENT_CODE_FIELDS[category][0]
        duplicate_file = self.env["qlk.client.file"].sudo().with_context(active_test=False).search(
            [
                ("id", "!=", project.client_file_id.id),
                ("company_id", "=", company.id),
                ("service_profile_type", "=", category),
                (code_field, "=", client_code),
            ],
            limit=1,
        )
        if duplicate_file:
            raise ValidationError(
                _(
                    "Client code %(code)s is assigned to more than one Client File. "
                    "Project numbering cannot continue without creating duplicate Service Codes."
                )
                % {"code": client_code}
            )
        self._lock("project", company.id, project.client_file_id.id, category)
        # MAX + advisory locking is independent from the number of projects in
        # other client files and prevents concurrent duplicate allocation.
        self.env.cr.execute(
            """
            SELECT COALESCE(
                       MAX(
                           CASE
                               WHEN project_sequence > 0 THEN project_sequence
                               WHEN split_part(service_code, '/', 2) ~ '^[0-9]+$'
                                   THEN split_part(service_code, '/', 2)::integer
                               ELSE 0
                           END
                       ),
                       0
                   ) + 1
              FROM qlk_project
             WHERE client_file_id = %s
               AND company_id = %s
               AND id != %s
            """,
            [project.client_file_id.id, company.id, project.id],
        )
        sequence = self.env.cr.fetchone()[0]
        # Litigation degrees belong to cases, never to the project identifier.
        code = "%s/%s" % (client_code, sequence)
        if self.env["qlk.project"].sudo().with_context(active_test=False).search_count(
            [("company_id", "=", company.id), ("service_code", "=", code), ("id", "!=", project.id)]
        ):
            raise ValidationError(
                _("Service Code %(code)s already exists. Check the Client File code and project records.")
                % {"code": code}
            )
        return {
            "service_category": category,
            "client_legal_code": client_code,
            "project_sequence": sequence,
            "project_code": code,
            "service_code": code,
        }

    @api.model
    def _record_degree_code(self, vals, record=False):
        degree_id = vals.get("litigation_degree_id")
        if not degree_id and record:
            degree_id = record.litigation_degree_id.id
        degree = self.env["qlk.litigation.degree"].browse(degree_id)
        if not degree.exists():
            raise ValidationError(_("Select a litigation degree for this case."))
        return degree.code

    @api.model
    def _generate_record_code_vals(self, model_name, vals, service_code, record=False, reserved_sequences=None):
        project_id = vals.get("project_id") or (record.project_id.id if record and record.project_id else False)
        project = self.env["qlk.project"].sudo().browse(project_id)
        if not project.exists():
            return vals
        project._ensure_service_code()
        category = self._service_category(service_code)
        company = project.company_id or self.env.company
        self._lock("record", company.id, model_name, project.id)
        domain = [("project_id", "=", project.id)]
        if record:
            domain.append(("id", "!=", record.id))
        same_project = bool(record and record.project_id and record.project_id.id == project.id)
        sequence = vals.get("record_sequence") or (record.record_sequence if same_project and record else 0)
        reserved_key = (model_name, project.id)
        reserved = reserved_sequences.setdefault(reserved_key, set()) if reserved_sequences is not None else set()
        if not sequence:
            sequence = self._get_next_available_sequence(
                model_name,
                "record_sequence",
                domain,
                parser=self._parse_record_sequence,
            )
            while sequence in reserved:
                sequence += 1
        if reserved_sequences is not None:
            reserved.add(sequence)
        if category == "litigation":
            degree_code = self._record_degree_code(vals, record=record)
            project_parts = (project.service_code or "").split("/")
            if len(project_parts) >= 3 and project_parts[-1] in {"F", "A", "C", "E"}:
                project_parts[-1] = degree_code
                code = "/".join(project_parts)
            else:
                code = "%s/%s" % (project.service_code, degree_code)
        else:
            code = "%s/%s" % (project.service_code, sequence)
        vals.update(
            {
                "service_category": category,
                "client_legal_code": project.client_legal_code or project.service_code.split("/", 1)[0],
                "project_legal_code": project.service_code,
                "record_sequence": sequence,
                "record_code": code,
                "service_code": code,
            }
        )
        return vals

    @api.model
    def _backfill_model_record_codes(self, model_name, service_code):
        Model = self.env[model_name].sudo().with_context(active_test=False)
        for record in Model.search([("project_id", "!=", False)], order="project_id, id"):
            vals = self._generate_record_code_vals(model_name, {}, service_code, record=record)
            updates = {
                key: value
                for key, value in vals.items()
                if key in record._fields and record[key] != value
            }
            if updates:
                record.with_context(
                    skip_engagement_case_validation=True,
                    skip_engagement_service_validation=True,
                    mail_notrack=True,
                ).write(updates)

    @api.model
    def backfill_legal_codes(self):
        if not self._ensure_client_file_profile_columns():
            return True
        ClientFile = self.env["qlk.client.file"].sudo().with_context(active_test=False)
        for client_file in ClientFile.search([], order="company_id, id"):
            service_codes = set(client_file.legal_service_type_ids.mapped("code"))
            if client_file.service_profile_type:
                service_codes.add(client_file.service_profile_type)
            for field_name, category in (
                ("litigation_client_code", "litigation"),
                ("corporate_client_code", "corporate"),
                ("arbitration_client_code", "arbitration"),
            ):
                if category in service_codes or client_file[field_name]:
                    self._generate_client_legal_code(client_file, category)

        Project = self.env["qlk.project"].sudo().with_context(active_test=False)
        for project in Project.search([("client_file_id", "!=", False)], order="client_file_id, id"):
            code = project.service_code or ""
            if not code or code.startswith("PRJ-") or "/" not in code:
                project.with_context(mail_notrack=True).write(self._generate_project_code(project))
            else:
                project_sequence = project.project_sequence or self._parse_project_sequence(code)
                client_code = code.split("/", 1)[0]
                updates = {
                    "service_category": self._service_category(project._primary_service_code()),
                    "client_legal_code": project.client_legal_code or client_code,
                    "project_sequence": project_sequence,
                    "project_code": project.project_code or code,
                }
                changed_values = {
                    key: value
                    for key, value in updates.items()
                    if key in project._fields and value and project[key] != value
                }
                if changed_values:
                    project.with_context(mail_notrack=True).write(changed_values)

        self._backfill_model_record_codes("qlk.case", "litigation")
        self._backfill_model_record_codes("qlk.corporate.case", "corporate")
        self._backfill_model_record_codes("qlk.arbitration.case", "arbitration")
        return True
