# -*- coding: utf-8 -*-

import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


SERVICE_SEQUENCE_CODES = {
    "litigation": "qlk.legal.service.litigation",
    "pre_litigation": "qlk.legal.service.litigation",
    "arbitration": "qlk.legal.service.arbitration",
    "corporate": "qlk.legal.service.corporate",
}

SERVICE_PREFIXES = {
    "litigation": "L",
    "pre_litigation": "L",
    "arbitration": "A",
    "corporate": "C",
}

CLIENT_CODE_FIELDS = {
    "litigation": "litigation_client_code",
    "pre_litigation": "litigation_client_code",
    "corporate": "corporate_client_code",
    "arbitration": "arbitration_client_code",
}

PROJECT_COUNTER_FIELDS = {
    "litigation": "litigation_project_next_number",
    "pre_litigation": "litigation_project_next_number",
    "corporate": "corporate_project_next_number",
    "arbitration": "arbitration_project_next_number",
}

CLIENT_CODE_SEQUENCE_CODES = {
    "litigation": "qlk.client.master.litigation",
    "pre_litigation": "qlk.client.master.litigation",
    "corporate": "qlk.client.master.corporate",
    "arbitration": "qlk.client.master.arbitration",
}

LEGAL_MANAGER_GROUPS = (
    "qlk_management.group_bd_manager",
    "qlk_management.group_el_manager",
    "qlk_management.group_client_file_manager",
    "qlk_management.group_project_manager",
)

LEVEL_XMLID_CODES = {
    "qlk_management.litigation_level_first_instance": "F",
    "qlk_management.litigation_level_appeal": "A",
    "qlk_management.litigation_level_cassation": "CA",
    "qlk_management.litigation_level_enforcement": "E",
}

LEGACY_RETAINER_SERVICE_CODES = {
    "litigation": ["litigation"],
    "corporate": ["corporate"],
    "arbitration": ["arbitration"],
    "litigation_corporate": ["litigation", "corporate"],
    "management_corporate": ["corporate"],
    "management_litigation": ["litigation"],
}


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
         LIMIT 1
        """,
        [table_name, column_name],
    )
    return bool(cr.fetchone())


def _migrate_legacy_legal_services(env, source_table, relation_table, owner_column):
    """Populate new legal-service tags from legacy service fields without dropping data."""
    cr = env.cr
    # أثناء ترقية الموديول قد يستدعي Odoo init قبل اكتمال إنشاء جدول أنواع الخدمات.
    # لذلك نتحقق من كل الجداول المطلوبة قبل تنفيذ SQL حتى لا تتوقف عملية الترقية.
    cr.execute(
        "SELECT to_regclass(%s), to_regclass(%s), to_regclass(%s)",
        [source_table, relation_table, "qlk_legal_service_type"],
    )
    if not all(cr.fetchone() or []):
        return

    def insert_mapping(column_name, legacy_value, service_code):
        if not _column_exists(cr, source_table, column_name):
            return
        cr.execute(
            """
            INSERT INTO %(relation_table)s (%(owner_column)s, service_type_id)
            SELECT source.id, service.id
              FROM %(source_table)s source
              JOIN qlk_legal_service_type service ON service.code = %%s
             WHERE source.%(column_name)s = %%s
               AND NOT EXISTS (
                   SELECT 1
                     FROM %(relation_table)s existing
                    WHERE existing.%(owner_column)s = source.id
                      AND existing.service_type_id = service.id
               )
            """
            % {
                "relation_table": relation_table,
                "owner_column": owner_column,
                "source_table": source_table,
                "column_name": column_name,
            },
            [service_code, legacy_value],
        )

    for code in SERVICE_PREFIXES:
        insert_mapping("service_type", code, code)
    for legacy_value, service_codes in LEGACY_RETAINER_SERVICE_CODES.items():
        for service_code in service_codes:
            insert_mapping("retainer_type", legacy_value, service_code)


class QlkLegalServiceType(models.Model):
    _name = "qlk.legal.service.type"
    _description = "Legal Service Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Selection(
        [
            ("litigation", "Litigation"),
            ("pre_litigation", "Pre-Litigation"),
            ("arbitration", "Arbitration"),
            ("corporate", "Corporate"),
        ],
        required=True,
        index=True,
    )
    prefix = fields.Char(required=True)
    color = fields.Integer(default=0)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Service code must be unique."),
    ]


class QlkClientFile(models.Model):
    _name = "qlk.client.file"
    _description = "Legal Client File"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "write_date desc, id desc"

    name = fields.Char(required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Client",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('customer_rank', '>', 0)]",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    email = fields.Char(related="partner_id.email", readonly=True)
    phone = fields.Char(related="partner_id.phone", readonly=True)
    mobile = fields.Char(related="partner_id.mobile", readonly=True)
    address = fields.Text(compute="_compute_address", store=True)
    legal_service_type_ids = fields.Many2many(
        "qlk.legal.service.type",
        "qlk_client_file_service_type_rel",
        "client_file_id",
        "service_type_id",
        string="Legal Services",
        tracking=True,
    )
    service_code_summary = fields.Char(compute="_compute_service_flags", store=True)
    has_litigation_service = fields.Boolean(compute="_compute_service_flags", store=True)
    has_pre_litigation_service = fields.Boolean(compute="_compute_service_flags", store=True)
    has_arbitration_service = fields.Boolean(compute="_compute_service_flags", store=True)
    has_corporate_service = fields.Boolean(compute="_compute_service_flags", store=True)
    litigation_client_code = fields.Char(string="Litigation Client Code", copy=False, readonly=True, index=True, tracking=True)
    corporate_client_code = fields.Char(string="Corporate Client Code", copy=False, readonly=True, index=True, tracking=True)
    arbitration_client_code = fields.Char(string="Arbitration Client Code", copy=False, readonly=True, index=True, tracking=True)
    litigation_project_next_number = fields.Integer(default=1, copy=False, readonly=True)
    corporate_project_next_number = fields.Integer(default=1, copy=False, readonly=True)
    arbitration_project_next_number = fields.Integer(default=1, copy=False, readonly=True)
    allowed_litigation_degree_ids = fields.Many2many(
        "qlk.litigation.degree",
        "qlk_client_file_litigation_degree_rel",
        "client_file_id",
        "degree_id",
        string="Allowed Litigation Degrees",
        tracking=True,
    )

    engagement_ids = fields.One2many("bd.engagement.letter", "client_file_id", string="Agreements")
    project_ids = fields.One2many("qlk.project", "client_file_id", string="Projects")
    litigation_case_ids = fields.One2many("qlk.case", "client_file_id", string="Litigation Cases")
    pre_litigation_ids = fields.One2many("qlk.pre.litigation", "client_file_id", string="Pre-Litigation")
    arbitration_case_ids = fields.One2many("qlk.arbitration.case", "client_file_id", string="Arbitration")
    corporate_case_ids = fields.One2many("qlk.corporate.case", "client_file_id", string="Corporate")

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_client_file_attachment_rel",
        "client_file_id",
        "attachment_id",
        string="Legal Attachments",
        tracking=True,
    )
    translation_attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_client_file_translation_attachment_rel",
        "client_file_id",
        "attachment_id",
        string="Translation Attachments",
        tracking=True,
    )

    litigation_count = fields.Integer(compute="_compute_counts", compute_sudo=True)
    pre_litigation_count = fields.Integer(compute="_compute_counts", compute_sudo=True)
    arbitration_count = fields.Integer(compute="_compute_counts", compute_sudo=True)
    corporate_count = fields.Integer(compute="_compute_counts", compute_sudo=True)
    agreement_count = fields.Integer(compute="_compute_counts", compute_sudo=True)
    project_count = fields.Integer(compute="_compute_counts", compute_sudo=True)
    attachment_count = fields.Integer(compute="_compute_counts", compute_sudo=True)
    poa_required = fields.Boolean(string="POA Required", default=True, tracking=True)
    poa_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("waiting_signature", "Waiting Client Signature"),
            ("uploaded", "Uploaded"),
            ("verified", "Verified"),
            ("expired", "Expired"),
        ],
        string="POA Status",
        default="draft",
        tracking=True,
        index=True,
    )
    poa_request_date = fields.Date(string="POA Request Date", tracking=True)
    poa_received_date = fields.Date(string="POA Received Date", tracking=True)
    poa_expiry_date = fields.Date(string="POA Expiry Date", tracking=True)
    poa_notes = fields.Text(string="POA Notes", tracking=True)
    poa_attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_client_file_poa_attachment_rel",
        "client_file_id",
        "attachment_id",
        string="POA Attachments",
        tracking=True,
    )
    poa_uploaded_by = fields.Many2one("res.users", string="POA Uploaded By", readonly=True, tracking=True)
    poa_verified_by = fields.Many2one("res.users", string="POA Verified By", readonly=True, tracking=True)
    poa_attachment_count = fields.Integer(string="POA Attachments", compute="_compute_counts", compute_sudo=True)
    poa_last_alert_date = fields.Date(string="Last POA Alert Date", copy=False, readonly=True)
    planned_hours = fields.Float(string="Planned Hours", compute="_compute_hours", store=True, compute_sudo=True)
    consumed_hours = fields.Float(string="Consumed Hours", compute="_compute_hours", store=True, compute_sudo=True)
    remaining_hours = fields.Float(string="Remaining Hours", compute="_compute_hours", store=True, compute_sudo=True)
    hours_state = fields.Selection(
        [("normal", "Normal"), ("warning", "Warning"), ("danger", "Overconsumed")],
        string="Hours State",
        compute="_compute_hours",
        compute_sudo=True,
        store=True,
    )

    litigation_next_number = fields.Integer(default=1, copy=False)
    pre_litigation_next_number = fields.Integer(default=1, copy=False)
    arbitration_next_number = fields.Integer(default=1, copy=False)
    corporate_next_number = fields.Integer(default=1, copy=False)
    lawyer_user_ids = fields.Many2many(
        "res.users",
        compute="_compute_lawyer_user_ids",
        store=True,
        string="Related Lawyers",
    )

    _sql_constraints = [
        ("partner_company_unique", "unique(partner_id, company_id)", "A client file already exists for this client."),
    ]

    def init(self):
        cr = self.env.cr
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS litigation_client_code varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS corporate_client_code varchar")
        cr.execute("ALTER TABLE qlk_client_file ADD COLUMN IF NOT EXISTS arbitration_client_code varchar")
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
        cr.execute(
            """
            UPDATE qlk_client_file
               SET litigation_project_next_number = COALESCE(litigation_project_next_number, 1),
                   corporate_project_next_number = COALESCE(corporate_project_next_number, 1),
                   arbitration_project_next_number = COALESCE(arbitration_project_next_number, 1),
                   poa_required = COALESCE(poa_required, true),
                   poa_status = COALESCE(poa_status, 'draft')
            """
        )
        cr.execute(
            "SELECT to_regclass(%s), to_regclass(%s)",
            ["qlk_client_file_service_type_rel", "qlk_legal_service_type"],
        )
        if all(cr.fetchone() or []):
            cr.execute(
                """
                UPDATE qlk_client_file client
                   SET poa_required = false,
                       poa_status = COALESCE(poa_status, 'draft')
                 WHERE NOT EXISTS (
                       SELECT 1
                         FROM qlk_client_file_service_type_rel rel
                         JOIN qlk_legal_service_type service ON service.id = rel.service_type_id
                        WHERE rel.client_file_id = client.id
                          AND service.code IN ('litigation', 'pre_litigation')
                   )
                """
            )

    @api.model
    def _service_category(self, service_code):
        return "litigation" if service_code in ("litigation", "pre_litigation") else service_code

    def _ensure_client_service_code(self, service_code):
        self.ensure_one()
        category = self._service_category(service_code)
        field_name = CLIENT_CODE_FIELDS.get(category)
        sequence_code = CLIENT_CODE_SEQUENCE_CODES.get(category)
        if not field_name or not sequence_code:
            raise ValidationError(_("Unsupported legal service type for client code."))
        if self[field_name]:
            return self[field_name]
        sequence = self.env["ir.sequence"].with_company(self.company_id or self.env.company)
        code = sequence.next_by_code(sequence_code)
        while code and self.sudo().search_count([
            (field_name, "=", code),
            ("company_id", "=", (self.company_id or self.env.company).id),
            ("id", "!=", self.id),
        ]):
            code = sequence.next_by_code(sequence_code)
        if not code:
            prefix = SERVICE_PREFIXES.get(category, "L")
            existing = self.sudo().search_count([(field_name, "!=", False), ("company_id", "=", self.company_id.id)])
            code = "%s%03d" % (prefix, existing + 1)
            while self.sudo().search_count([
                (field_name, "=", code),
                ("company_id", "=", (self.company_id or self.env.company).id),
                ("id", "!=", self.id),
            ]):
                existing += 1
                code = "%s%03d" % (prefix, existing + 1)
        # أثناء ترقية الموديول قد لا تكون جداول Many2many أنشئت بعد؛ لذلك نتجنب ORM write والتتبع هنا.
        self.env.cr.execute(
            "UPDATE qlk_client_file SET %s = %%s WHERE id = %%s" % field_name,
            [code, self.id],
        )
        self.invalidate_recordset([field_name])
        return code

    def _next_project_number(self, service_code):
        self.ensure_one()
        category = self._service_category(service_code)
        field_name = PROJECT_COUNTER_FIELDS.get(category)
        if not field_name:
            raise ValidationError(_("Unsupported legal service type for project numbering."))
        self.env.cr.execute("SELECT %s FROM qlk_client_file WHERE id = %%s FOR UPDATE" % field_name, [self.id])
        current = (self.env.cr.fetchone() or [1])[0] or 1
        self.env.cr.execute(
            "UPDATE qlk_client_file SET %s = %%s WHERE id = %%s" % field_name,
            [current + 1, self.id],
        )
        self.invalidate_recordset([field_name])
        return current

    def _next_project_service_code(self, service_code):
        self.ensure_one()
        client_code = self._ensure_client_service_code(service_code)
        number = self._next_project_number(service_code)
        code = "%s/%s" % (client_code, number)
        while self.env["qlk.project"].sudo().search_count([
            ("service_code", "=", code),
            ("company_id", "=", self.company_id.id),
        ]):
            number = self._next_project_number(service_code)
            code = "%s/%s" % (client_code, number)
        return code

    @api.depends("partner_id", "partner_id.street", "partner_id.street2", "partner_id.city", "partner_id.country_id")
    def _compute_address(self):
        for record in self:
            partner = record.partner_id
            parts = [
                partner.street,
                partner.street2,
                partner.city,
                partner.country_id.display_name if partner.country_id else False,
            ]
            record.address = "\n".join(part for part in parts if part)

    @api.depends("legal_service_type_ids", "legal_service_type_ids.code")
    def _compute_service_flags(self):
        for record in self:
            codes = set(record.legal_service_type_ids.mapped("code"))
            record.has_litigation_service = "litigation" in codes
            record.has_pre_litigation_service = "pre_litigation" in codes
            record.has_arbitration_service = "arbitration" in codes
            record.has_corporate_service = "corporate" in codes
            record.service_code_summary = ", ".join(record.legal_service_type_ids.mapped("name"))

    def _has_poa_service(self, service_ids=False):
        services = (
            self.env["qlk.legal.service.type"].browse(service_ids)
            if service_ids is not False
            else self.legal_service_type_ids
        )
        return bool({"litigation", "pre_litigation"}.intersection(services.mapped("code")))

    def _ensure_poa_applicable(self):
        for record in self:
            if not record._has_poa_service():
                raise UserError(_("POA is required only for Litigation or Pre-Litigation services."))

    def _poa_required_from_service_commands(self, commands):
        service_ids = self._extract_m2m_ids(commands)
        return self._has_poa_service(service_ids)

    def _service_ids_after_commands(self, commands):
        self.ensure_one()
        service_ids = set(self.legal_service_type_ids.ids)
        for command in commands or []:
            if not isinstance(command, (list, tuple)) or not command:
                continue
            if command[0] == 6:
                service_ids = set(command[2])
            elif command[0] == 4:
                service_ids.add(command[1])
            elif command[0] == 3:
                service_ids.discard(command[1])
            elif command[0] == 5:
                service_ids.clear()
        return list(service_ids)

    @api.onchange("legal_service_type_ids")
    def _onchange_legal_service_type_ids_poa_required(self):
        for record in self:
            record.poa_required = record._has_poa_service()

    @api.depends(
        "engagement_ids",
        "project_ids",
        "litigation_case_ids",
        "pre_litigation_ids",
        "arbitration_case_ids",
        "corporate_case_ids",
        "attachment_ids",
        "translation_attachment_ids",
        "poa_attachment_ids",
    )
    def _compute_counts(self):
        for record in self:
            record.litigation_count = len(record.litigation_case_ids)
            record.pre_litigation_count = len(record.pre_litigation_ids)
            record.arbitration_count = len(record.arbitration_case_ids)
            record.corporate_count = len(record.corporate_case_ids)
            record.agreement_count = len(record.engagement_ids)
            record.project_count = len(record.project_ids)
            record.attachment_count = len(record.attachment_ids | record.translation_attachment_ids)
            record.poa_attachment_count = len(record.poa_attachment_ids)

    @api.depends("project_ids.planned_hours", "project_ids.consumed_hours", "project_ids.remaining_hours", "project_ids.hours_state")
    def _compute_hours(self):
        for record in self:
            record.planned_hours = sum(record.project_ids.mapped("planned_hours"))
            record.consumed_hours = sum(record.project_ids.mapped("consumed_hours"))
            record.remaining_hours = record.planned_hours - record.consumed_hours
            if record.remaining_hours < 0:
                record.hours_state = "danger"
            elif record.planned_hours and record.consumed_hours / record.planned_hours >= 0.8:
                record.hours_state = "warning"
            else:
                record.hours_state = "normal"

    @api.depends(
        "engagement_ids.lawyer_user_id",
        "engagement_ids.lawyer_ids.user_id",
        "litigation_case_ids.lawyer_id",
        "pre_litigation_ids.lawyer_user_id",
        "arbitration_case_ids.responsible_user_id",
        "corporate_case_ids.responsible_user_id",
    )
    def _compute_lawyer_user_ids(self):
        for record in self:
            users = self.env["res.users"]
            users |= record.engagement_ids.mapped("lawyer_user_id")
            users |= record.engagement_ids.mapped("lawyer_ids.user_id")
            users |= record.litigation_case_ids.mapped("lawyer_id")
            users |= record.pre_litigation_ids.mapped("lawyer_user_id")
            users |= record.arbitration_case_ids.mapped("responsible_user_id")
            users |= record.corporate_case_ids.mapped("responsible_user_id")
            record.lawyer_user_ids = users

    @api.model_create_multi
    def create(self, vals_list):
        service_model = self.env["qlk.legal.service.type"]
        for vals in vals_list:
            # Keep older XML/RPC payloads upgrade-safe while the canonical field is
            # legal_service_type_ids.
            if vals.get("service_type_ids") and not vals.get("legal_service_type_ids"):
                vals["legal_service_type_ids"] = vals.pop("service_type_ids")
            vals.pop("client_code", None)
            vals.pop("retainer_type", None)
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            partner = self.env["res.partner"].browse(vals.get("partner_id"))
            if partner.exists() and not vals.get("name"):
                vals["name"] = partner.display_name
            if not vals.get("legal_service_type_ids"):
                codes = vals.pop("_service_codes", False) or ["litigation"]
                vals["legal_service_type_ids"] = [(6, 0, service_model._ids_from_codes(codes))]
            elif not self._extract_m2m_ids(vals.get("legal_service_type_ids")):
                vals["legal_service_type_ids"] = [(6, 0, service_model._ids_from_codes(["litigation"]))]
            vals["poa_required"] = self._poa_required_from_service_commands(vals["legal_service_type_ids"])
            if not vals["poa_required"]:
                vals.setdefault("poa_status", "draft")
        records = super().create(vals_list)
        records._sync_attachments_from_agreements()
        for record in records.filtered(lambda item: item.poa_required and item.poa_status == "draft"):
            record.with_context(skip_poa_manager_check=True).action_request_poa()
        return records

    def write(self, vals):
        vals = dict(vals)
        if vals.get("service_type_ids") and not vals.get("legal_service_type_ids"):
            vals["legal_service_type_ids"] = vals.pop("service_type_ids")
        vals.pop("client_code", None)
        vals.pop("retainer_type", None)
        if "legal_service_type_ids" in vals:
            vals["poa_required"] = (
                self._has_poa_service(self._service_ids_after_commands(vals["legal_service_type_ids"]))
                if len(self) == 1
                else self._poa_required_from_service_commands(vals["legal_service_type_ids"])
            )
            if not vals["poa_required"]:
                vals.update(
                    {
                        "poa_status": "draft",
                        "poa_request_date": False,
                        "poa_received_date": False,
                        "poa_expiry_date": False,
                        "poa_notes": False,
                    }
                )
        result = super().write(vals)
        if not self.env.context.get("skip_client_file_attachment_sync") and "engagement_ids" in vals:
            self._sync_attachments_from_agreements()
        if "poa_attachment_ids" in vals and not self.env.context.get("skip_poa_auto_status"):
            uploaded = self.filtered(lambda item: item.poa_attachment_ids and item.poa_status not in ("verified", "expired"))
            if uploaded:
                uploaded.with_context(skip_poa_auto_status=True, mail_notrack=True).write(
                    {
                        "poa_status": "uploaded",
                        "poa_received_date": fields.Date.context_today(self),
                        "poa_uploaded_by": self.env.user.id,
                    }
                )
                uploaded._propagate_poa_attachments()
        return result

    @api.model
    def _next_legal_service_code(self, service_code, company=False):
        primary = service_code if service_code in SERVICE_SEQUENCE_CODES else "litigation"
        sequence_code = SERVICE_SEQUENCE_CODES.get(primary, SERVICE_SEQUENCE_CODES["litigation"])
        company = company or self.env.company
        return self.env["ir.sequence"].with_company(company).next_by_code(sequence_code) or _("New")

    @api.model
    def _primary_service_code(self, codes):
        code_set = set(codes)
        if code_set == {"corporate"}:
            return "corporate"
        if code_set == {"arbitration"}:
            return "arbitration"
        return "litigation"

    @api.model
    def _extract_m2m_ids(self, commands):
        ids = []
        for command in commands or []:
            if isinstance(command, (list, tuple)) and command:
                if command[0] == 6:
                    ids.extend(command[2])
                elif command[0] == 4:
                    ids.append(command[1])
        return ids

    def _sync_attachments_from_agreements(self):
        for record in self:
            normal, translation = record._collect_agreement_attachments()
            missing_normal = normal - record.attachment_ids
            missing_translation = translation - record.translation_attachment_ids
            values = {}
            if missing_normal:
                values["attachment_ids"] = [(4, attachment_id) for attachment_id in missing_normal.ids]
            if missing_translation:
                values["translation_attachment_ids"] = [
                    (4, attachment_id) for attachment_id in missing_translation.ids
                ]
            if values:
                record.with_context(
                    skip_client_file_attachment_sync=True,
                    mail_notrack=True,
                ).write(values)

    def _collect_agreement_attachments(self):
        self.ensure_one()
        normal = self.env["ir.attachment"]
        translation = self.env["ir.attachment"]
        for engagement in self.engagement_ids:
            normal |= engagement.client_attachment_ids
            normal |= engagement.signed_document_ids
            if engagement.signed_document_id:
                normal |= engagement.signed_document_id
            translation |= engagement.translation_attachment_ids
        return normal, translation

    def _collect_transfer_attachments(self):
        self.ensure_one()
        normal, translation = self._collect_agreement_attachments()
        return (self.attachment_ids | self.poa_attachment_ids | normal), (self.translation_attachment_ids | translation)

    def _check_poa_manager(self):
        if self.env.context.get("skip_poa_manager_check"):
            return True
        if any(self.env.user.has_group(group) for group in LEGAL_MANAGER_GROUPS):
            return True
        raise UserError(_("Only an office or legal manager can process POA actions."))

    def _poa_office_email(self):
        return "mp.office@alhadhrilawfirm.com"

    def _poa_lawyer_emails(self):
        self.ensure_one()
        emails = set()
        for user in self.lawyer_user_ids.filtered("email"):
            emails.add(user.email)
        return sorted(emails)

    def _poa_request_values(self):
        self.ensure_one()
        return {
            "client": self.partner_id.display_name or self.name,
            "file": self.name,
            "services": self.service_code_summary or "-",
            "lawyers": ", ".join(self.lawyer_user_ids.mapped("name")) or "-",
            "responsible": self.env.user.display_name,
            "date": self.poa_request_date or fields.Date.context_today(self),
        }

    def _send_poa_request_email(self):
        template = self.env.ref("qlk_management.mail_template_client_file_poa_request", raise_if_not_found=False)
        for record in self:
            if template:
                template.sudo().send_mail(record.id, force_send=True, raise_exception=False)
                continue
            values = record._poa_request_values()
            body = _(
                "Client: %(client)s<br/>Client File: %(file)s<br/>Legal Service Type: %(services)s<br/>"
                "Assigned Lawyers: %(lawyers)s<br/>Responsible User: %(responsible)s<br/>Request Date: %(date)s"
            ) % values
            self.env["mail.mail"].sudo().create(
                {
                    "subject": _("POA Request Required - Client File %s") % record.name,
                    "email_to": record._poa_office_email(),
                    "body_html": body,
                }
            ).send()

    def _send_poa_alert_email(self, subject, body):
        for record in self:
            recipients = [record._poa_office_email()] + record._poa_lawyer_emails()
            recipients = [email for email in recipients if email]
            if not recipients:
                continue
            self.env["mail.mail"].sudo().create(
                {
                    "subject": subject,
                    "email_to": ",".join(sorted(set(recipients))),
                    "body_html": body,
                }
            ).send()
            record.message_post(body=body)

    def _schedule_poa_activity(self, summary, note=False):
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return
        for record in self:
            users = record.lawyer_user_ids.filtered("active") | self.env.user
            for user in users:
                record.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    summary=summary,
                    note=note or summary,
                )

    def action_request_poa(self):
        today = fields.Date.context_today(self)
        for record in self:
            record._ensure_poa_applicable()
            record._check_poa_manager()
            record.write(
                {
                    "poa_required": True,
                    "poa_status": "requested",
                    "poa_request_date": record.poa_request_date or today,
                }
            )
        self._send_poa_request_email()
        for record in self:
            record.message_post(body=_("POA request email has been sent to the office manager."))
        self._schedule_poa_activity(_("POA request sent"), _("Follow up signed POA upload and verification."))
        return True

    def action_upload_poa(self):
        self.ensure_one()
        self._ensure_poa_applicable()
        self._check_poa_manager()
        return {
            "type": "ir.actions.act_window",
            "name": _("Upload POA"),
            "res_model": "qlk.poa.upload.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_client_file_id": self.id},
        }

    def action_create_poa(self):
        today = fields.Date.context_today(self)
        for record in self:
            record._ensure_poa_applicable()
            record._check_poa_manager()
            content = _("Power of Attorney internal request for %s generated on %s.") % (record.display_name, today)
            attachment = self.env["ir.attachment"].sudo().create(
                {
                    "name": _("POA Request - %s.txt") % record.name,
                    "type": "binary",
                    "datas": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "res_model": record._name,
                    "res_id": record.id,
                    "mimetype": "text/plain",
                }
            )
            record.write({"attachment_ids": [(4, attachment.id)]})
            record.message_post(body=_("Internal POA document has been created."), attachment_ids=[attachment.id])
        return True

    def action_verify_poa(self):
        today = fields.Date.context_today(self)
        for record in self:
            record._ensure_poa_applicable()
            record._check_poa_manager()
            if not record.poa_attachment_ids:
                raise UserError(_("Upload the signed POA before verification."))
            if record.poa_expiry_date and record.poa_expiry_date < today:
                raise UserError(_("The uploaded POA is already expired."))
            record.write(
                {
                    "poa_status": "verified",
                    "poa_verified_by": self.env.user.id,
                    "poa_received_date": record.poa_received_date or today,
                }
            )
            record._propagate_poa_attachments()
            record.message_post(body=_("POA has been verified."))
        return True

    def action_open_poa_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("POA Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.poa_attachment_ids.ids)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def _propagate_poa_attachments(self):
        for record in self:
            if not record.poa_attachment_ids:
                continue
            attachment_commands = [(4, attachment_id) for attachment_id in record.poa_attachment_ids.ids]
            for targets in (
                record.project_ids,
                record.litigation_case_ids,
                record.pre_litigation_ids,
                record.arbitration_case_ids,
                record.corporate_case_ids,
            ):
                if targets and "attachment_ids" in targets._fields:
                    targets.sudo().write({"attachment_ids": attachment_commands})

    def _ensure_poa_verified(self):
        for record in self:
            if record.poa_required and record.poa_status != "verified":
                raise ValidationError(_("Cannot proceed until the signed Power of Attorney (POA) is uploaded and verified."))
        return True

    @api.model
    def _cron_check_poa_alerts(self):
        today = fields.Date.context_today(self)
        expired = self.search(
            [
                ("poa_required", "=", True),
                ("poa_expiry_date", "!=", False),
                ("poa_expiry_date", "<", today),
                ("poa_status", "!=", "expired"),
            ]
        )
        if expired:
            expired.write({"poa_status": "expired", "poa_last_alert_date": today})
            expired._send_poa_alert_email(
                _("POA expired"),
                _("A Power of Attorney has expired. Please renew it before proceeding with legal work."),
            )

        threshold = fields.Date.subtract(today, days=3)
        missing = self.search(
            [
                ("poa_required", "=", True),
                ("poa_status", "in", ["requested", "waiting_signature"]),
                ("poa_request_date", "!=", False),
                ("poa_request_date", "<=", threshold),
                "|",
                ("poa_last_alert_date", "=", False),
                ("poa_last_alert_date", "<", today),
            ]
        )
        if missing:
            missing.write({"poa_last_alert_date": today})
            missing._send_poa_alert_email(
                _("POA pending signature"),
                _("The POA is still missing after the allowed follow-up period."),
            )
        return True

    def _ensure_service_allowed(self, service_code):
        self.ensure_one()
        if service_code not in set(self.legal_service_type_ids.mapped("code")):
            raise UserError(_("This client file is not configured for this service."))

    def _base_service_defaults(self, service_code):
        self.ensure_one()
        self._ensure_service_allowed(service_code)
        engagement = self.engagement_ids.sorted("date", reverse=True)[:1]
        lawyer = engagement.lawyer_employee_id if engagement else self.env["hr.employee"]
        return {
            "default_client_file_id": self.id,
            "default_engagement_id": engagement.id if engagement else False,
            "default_company_id": self.company_id.id,
            "default_name": self.name,
            "default_subject": self.name,
            "default_lawyer_employee_id": lawyer.id if lawyer else False,
            "default_employee_id": lawyer.id if lawyer else False,
            "skip_engagement_service_validation": True,
            "skip_engagement_case_validation": True,
        }

    def _open_related(self, model_name, title):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_name,
            "view_mode": "list,form",
            "domain": [("client_file_id", "=", self.id)],
            "context": {"default_client_file_id": self.id},
        }

    def action_open_litigation(self):
        return self._open_related("qlk.case", _("Litigation"))

    def action_open_pre_litigation(self):
        return self._open_related("qlk.pre.litigation", _("Pre-Litigation"))

    def action_open_arbitration(self):
        return self._open_related("qlk.arbitration.case", _("Arbitration"))

    def action_open_corporate(self):
        return self._open_related("qlk.corporate.case", _("Corporate"))

    def action_open_agreements(self):
        return self._open_related("bd.engagement.letter", _("Agreements"))

    def action_open_projects(self):
        return self._open_related("qlk.project", _("Projects"))

    def action_open_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [("id", "in", (self.attachment_ids | self.translation_attachment_ids).ids)],
        }

    def action_create_litigation(self):
        raise UserError(_("Legal services must be created from the related project."))

    def action_create_pre_litigation(self):
        raise UserError(_("Legal services must be created from the related project."))

    def action_create_arbitration(self):
        raise UserError(_("Legal services must be created from the related project."))

    def action_create_corporate(self):
        raise UserError(_("Legal services must be created from the related project."))

    def action_create_project(self):
        self.ensure_one()
        self.env["qlk.project"]._ensure_legal_manager()
        approved_engagements = self.engagement_ids.filtered(
            lambda item: item.state == "approved_client"
        ).sorted("date", reverse=True)
        engagement = approved_engagements.filtered(lambda item: not item.project_id)[:1] or approved_engagements[:1]
        if not engagement:
            raise UserError(_("No client-approved engagement letter was found for this client file."))
        if engagement.project_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Project"),
                "res_model": "qlk.project",
                "res_id": engagement.project_id.id,
                "view_mode": "form",
                "target": "current",
            }
        project_vals = self._prepare_project_vals_from_engagement(engagement)
        project = self.env["qlk.project"].with_context(
            mail_create_nosubscribe=True,
            mail_auto_subscribe_no_notify=True,
        ).create(project_vals)
        engagement.with_context(
            mail_create_nosubscribe=True,
            mail_auto_subscribe_no_notify=True,
        ).write({"project_id": project.id, "client_file_id": self.id})
        self.message_post(body=_("Project %s has been created from this client file.") % project.display_name)
        return {
            "type": "ir.actions.act_window",
            "name": _("Project"),
            "res_model": "qlk.project",
            "res_id": project.id,
            "view_mode": "form",
            "target": "current",
        }

    def _prepare_project_vals_from_engagement(self, engagement):
        self.ensure_one()
        services = (
            engagement._get_legal_service_type_ids_for_transfer()
            if hasattr(engagement, "_get_legal_service_type_ids_for_transfer")
            else engagement.legal_service_type_ids
        ) or self.legal_service_type_ids
        litigation_degrees = (
            engagement._get_allowed_litigation_degree_ids_for_transfer()
            if hasattr(engagement, "_get_allowed_litigation_degree_ids_for_transfer")
            else engagement.litigation_degree_ids
        ) or self.allowed_litigation_degree_ids
        normal_attachments, translation_attachments = self._collect_transfer_attachments()
        responsible_users = engagement.lawyer_user_id | engagement.lawyer_ids.mapped("user_id") | engagement.reviewer_id
        planned_hours = (
            engagement.planned_hours
            or engagement.agreed_hours
            or engagement.allocated_hours
            or engagement.estimated_hours
            or 0.0
        )
        vals = {
            "client_file_id": self.id,
            "client_id": engagement.partner_id.id or self.partner_id.id,
            "engagement_letter_id": engagement.id,
            "contact_person_ids": [(6, 0, engagement.lawyer_ids.ids)],
            "phone": engagement.partner_id.phone or engagement.partner_id.mobile,
            "email": engagement.partner_id.email,
            "lawyer_id": engagement.lawyer_employee_id.id,
            "responsible_user_ids": [(6, 0, responsible_users.ids)],
            "contract_type": engagement.contract_type,
            "billing_type": engagement.billing_type,
            "currency_id": engagement.currency_id.id,
            "start_date": engagement.year_start_date or engagement.date,
            "end_date": engagement.year_end_date,
            "retainer_type": engagement.retainer_type,
            "agreed_hours": planned_hours,
            "planned_hours": planned_hours,
            "total_hours": engagement.total_hours_used,
            "description": engagement.description or engagement.services_description,
            "scope_details": engagement.scope_of_work,
            "contract_terms": engagement.scope_of_work,
            "payment_terms": engagement.payment_terms,
            "notes": engagement.legal_note or engagement.contact_details,
            "attachment_ids": [(6, 0, normal_attachments.ids)],
            "translation_attachment_ids": [(6, 0, translation_attachments.ids)],
        }
        if services:
            vals["legal_service_type_ids"] = [(6, 0, services.ids)]
            if len(services) == 1:
                vals["service_type"] = services.code
        if litigation_degrees:
            vals["litigation_degree_ids"] = [(6, 0, litigation_degrees.ids)]
            vals["allowed_litigation_degree_ids"] = [(6, 0, litigation_degrees.ids)]
        return vals

    def _new_service_action(self, model_name, title, context):
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_name,
            "view_mode": "form",
            "target": "current",
            "context": context,
        }


class QlkLegalServiceTypeTools(models.Model):
    _inherit = "qlk.legal.service.type"

    @api.model
    def _ids_from_codes(self, codes):
        return self.search([("code", "in", list(set(codes)))], order="sequence, id").ids


class BDEngagementLetterClientFile(models.Model):
    _inherit = "bd.engagement.letter"

    client_file_id = fields.Many2one(
        "qlk.client.file",
        string="Client File",
        copy=False,
        ondelete="set null",
        tracking=True,
    )
    client_file_count = fields.Integer(compute="_compute_client_file_count")
    legal_service_type_ids = fields.Many2many(
        "qlk.legal.service.type",
        "bd_engagement_legal_service_type_rel",
        "engagement_id",
        "service_type_id",
        string="Legal Services",
        tracking=True,
    )
    has_litigation_service = fields.Boolean(compute="_compute_engagement_service_flags", store=True)
    has_pre_litigation_service = fields.Boolean(compute="_compute_engagement_service_flags", store=True)
    has_arbitration_service = fields.Boolean(compute="_compute_engagement_service_flags", store=True)
    has_corporate_service = fields.Boolean(compute="_compute_engagement_service_flags", store=True)

    def init(self):
        super().init()
        _migrate_legacy_legal_services(
            self.env,
            "bd_engagement_letter",
            "bd_engagement_legal_service_type_rel",
            "engagement_id",
        )

    @api.depends("client_file_id", "partner_id")
    def _compute_client_file_count(self):
        for record in self:
            record.client_file_count = 1 if record._get_existing_client_file() else 0

    @api.depends("legal_service_type_ids", "legal_service_type_ids.code", "service_type")
    def _compute_engagement_service_flags(self):
        for record in self:
            codes = set(record.legal_service_type_ids.mapped("code"))
            if not codes and record.service_type and record.service_type != "mixed":
                codes.add(record.service_type)
            record.has_litigation_service = "litigation" in codes
            record.has_pre_litigation_service = "pre_litigation" in codes
            record.has_arbitration_service = "arbitration" in codes
            record.has_corporate_service = "corporate" in codes

    @api.model_create_multi
    def create(self, vals_list):
        service_model = self.env["qlk.legal.service.type"]
        for vals in vals_list:
            if not vals.get("legal_service_type_ids"):
                vals["legal_service_type_ids"] = [(6, 0, service_model._ids_from_codes(self._service_codes_from_vals(vals)))]
        records = super().create(vals_list)
        for record in records:
            existing = record._get_existing_client_file()
            if existing:
                record.with_context(mail_notrack=True).client_file_id = existing.id
                record._merge_services_into_client_file(existing)
        return records

    def write(self, vals):
        vals = dict(vals)
        service_input_fields = {"service_type", "retainer_type"}
        if service_input_fields.intersection(vals) and not vals.get("legal_service_type_ids"):
            for record in self:
                code_vals = {
                    "service_type": vals.get("service_type", record.service_type),
                    "retainer_type": vals.get("retainer_type", record.retainer_type),
                }
                service_ids = self.env["qlk.legal.service.type"]._ids_from_codes(self._service_codes_from_vals(code_vals))
                vals["legal_service_type_ids"] = [(6, 0, service_ids)]
                break
        result = super().write(vals)
        if {
            "legal_service_type_ids",
            "litigation_degree_ids",
            "allowed_litigation_degree_ids",
            "client_file_id",
            "client_attachment_ids",
            "translation_attachment_ids",
            "signed_document_ids",
        }.intersection(vals):
            for record in self.filtered("client_file_id"):
                record._merge_services_into_client_file(record.client_file_id)
                record.client_file_id._sync_attachments_from_agreements()
        return result

    @api.model
    def _service_codes_from_vals(self, vals):
        service_type = vals.get("service_type")
        retainer_type = vals.get("retainer_type")
        if service_type and service_type != "mixed":
            return [service_type]
        return self._service_codes_from_retainer(retainer_type)

    @api.model
    def _service_codes_from_retainer(self, retainer_type):
        return LEGACY_RETAINER_SERVICE_CODES.get(retainer_type) or ["litigation"]

    def _service_allows(self, service):
        self.ensure_one()
        if self.legal_service_type_ids:
            return service in set(self.legal_service_type_ids.mapped("code"))
        return super()._service_allows(service)

    def _get_legal_service_type_ids_for_transfer(self):
        self.ensure_one()
        services = self.legal_service_type_ids
        if not services:
            service_model = self.env["qlk.legal.service.type"]
            services = service_model.browse(
                service_model._ids_from_codes(
                    self._service_codes_from_vals(
                        {"service_type": self.service_type, "retainer_type": self.retainer_type}
                    )
                )
            )
        return services

    def _get_allowed_litigation_degree_ids_for_transfer(self):
        self.ensure_one()
        return self.allowed_litigation_degree_ids or self.litigation_degree_ids

    def _get_existing_client_file(self):
        self.ensure_one()
        if self.client_file_id:
            return self.client_file_id
        if not self.partner_id:
            return self.env["qlk.client.file"]
        return self.env["qlk.client.file"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("company_id", "=", (self.company_id or self.env.company).id),
            ],
            limit=1,
        )

    def _merge_services_into_client_file(self, client_file):
        self.ensure_one()
        services = client_file.legal_service_type_ids | self._get_legal_service_type_ids_for_transfer()
        degrees = client_file.allowed_litigation_degree_ids | self._get_allowed_litigation_degree_ids_for_transfer()
        vals = {}
        if services:
            vals["legal_service_type_ids"] = [(6, 0, services.ids)]
        if degrees:
            vals["allowed_litigation_degree_ids"] = [(6, 0, degrees.ids)]
        if vals:
            client_file.write(vals)

    def action_create_client_file(self):
        self.ensure_one()
        if self.state != "approved_client":
            raise UserError(_("Client files can only be created from client-approved engagement letters."))
        if not self.partner_id:
            raise UserError(_("Select a client before creating a client file."))
        client_file = self._get_existing_client_file()
        if not client_file:
            services = self._get_legal_service_type_ids_for_transfer()
            litigation_degrees = self._get_allowed_litigation_degree_ids_for_transfer()
            client_file = self.env["qlk.client.file"].create(
                {
                    "name": self.partner_id.display_name,
                    "partner_id": self.partner_id.id,
                    "company_id": (self.company_id or self.env.company).id,
                    "legal_service_type_ids": [(6, 0, services.ids)],
                    "allowed_litigation_degree_ids": [(6, 0, litigation_degrees.ids)],
                }
            )
        self.client_file_id = client_file.id
        self._merge_services_into_client_file(client_file)
        client_file._sync_attachments_from_agreements()
        return self.action_open_client_file()

    def action_open_client_file(self):
        self.ensure_one()
        client_file = self._get_existing_client_file()
        if not client_file:
            raise UserError(_("No client file exists for this engagement letter."))
        if not self.client_file_id:
            self.client_file_id = client_file.id
            self._merge_services_into_client_file(client_file)
        return {
            "type": "ir.actions.act_window",
            "name": _("Client File"),
            "res_model": "qlk.client.file",
            "res_id": client_file.id,
            "view_mode": "form",
            "target": "current",
        }


class QlkProjectClientFile(models.Model):
    _inherit = "qlk.project"

    client_file_id = fields.Many2one("qlk.client.file", string="Client File", ondelete="set null", tracking=True)
    poa_required = fields.Boolean(string="POA Required", related="client_file_id.poa_required", readonly=True)
    poa_status = fields.Selection(
        related="client_file_id.poa_status",
        string="POA Status",
        readonly=True,
        store=True,
    )
    poa_attachment_ids = fields.Many2many(
        "ir.attachment",
        related="client_file_id.poa_attachment_ids",
        string="POA Attachments",
        readonly=True,
    )
    poa_attachment_count = fields.Integer(
        string="POA Attachments",
        related="client_file_id.poa_attachment_count",
        readonly=True,
    )
    retainer_type = fields.Selection(
        [
            ("litigation", "Litigation"),
            ("corporate", "Corporate"),
            ("arbitration", "Arbitration"),
            ("litigation_corporate", "Litigation + Corporate"),
            ("management_corporate", "Management + Corporate"),
            ("management_litigation", "Management + Litigation"),
        ],
        string="Legacy Retainer Type",
        tracking=True,
        help="Legacy field kept for upgrade compatibility. Use Legal Services for new logic.",
    )
    legal_service_type_ids = fields.Many2many(
        "qlk.legal.service.type",
        "qlk_project_legal_service_type_rel",
        "project_id",
        "service_type_id",
        string="Legal Services",
        tracking=True,
    )
    has_litigation_service = fields.Boolean(compute="_compute_project_service_flags", store=True)
    has_pre_litigation_service = fields.Boolean(compute="_compute_project_service_flags", store=True)
    has_arbitration_service = fields.Boolean(compute="_compute_project_service_flags", store=True)
    has_corporate_service = fields.Boolean(compute="_compute_project_service_flags", store=True)

    def init(self):
        super().init()
        _migrate_legacy_legal_services(
            self.env,
            "qlk_project",
            "qlk_project_legal_service_type_rel",
            "project_id",
        )
        self.backfill_legal_codes()

    @api.model_create_multi
    def create(self, vals_list):
        service_model = self.env["qlk.legal.service.type"]
        for vals in vals_list:
            if vals.get("engagement_letter_id"):
                engagement = self.env["bd.engagement.letter"].browse(vals["engagement_letter_id"])
                vals.setdefault("client_file_id", engagement.client_file_id.id)
                if not vals.get("legal_service_type_ids"):
                    vals["legal_service_type_ids"] = [(6, 0, engagement.legal_service_type_ids.ids)]
            if not vals.get("legal_service_type_ids") and vals.get("service_type"):
                vals["legal_service_type_ids"] = [(6, 0, service_model._ids_from_codes([vals["service_type"]]))]
        return super().create(vals_list)

    @api.depends("legal_service_type_ids", "legal_service_type_ids.code", "service_type")
    def _compute_project_service_flags(self):
        for record in self:
            codes = record._legal_service_codes()
            record.has_litigation_service = "litigation" in codes
            record.has_pre_litigation_service = "pre_litigation" in codes
            record.has_arbitration_service = "arbitration" in codes
            record.has_corporate_service = "corporate" in codes

    def _legal_service_codes(self):
        self.ensure_one()
        return set(self.legal_service_type_ids.mapped("code") or ([self.service_type] if self.service_type else []))

    def _allows_legal_service(self, service_code):
        self.ensure_one()
        return service_code in self._legal_service_codes()


class ClientFileServiceMixin(models.AbstractModel):
    _name = "qlk.client.file.service.mixin"
    _description = "Client File Service Helpers"

    def _apply_client_file_defaults(self, vals, service_code):
        client_file = self.env["qlk.client.file"].browse(vals.get("client_file_id"))
        if not client_file.exists():
            return vals
        client_file._ensure_service_allowed(service_code)
        engagement = client_file.engagement_ids.sorted("date", reverse=True)[:1]
        vals.setdefault("engagement_id", engagement.id if engagement else False)
        vals.setdefault("company_id", client_file.company_id.id)
        self._apply_service_code_defaults(vals, service_code, client_file.company_id)
        self._apply_client_file_partner_defaults(vals, client_file, engagement)
        return vals

    def _apply_client_file_partner_defaults(self, vals, client_file, engagement):
        return vals

    def _apply_service_code_defaults(self, vals, service_code, company=False):
        if service_code == "litigation":
            base = self._legal_service_base_from_vals(vals) or self.env["qlk.client.file"]._next_legal_service_code(
                service_code, company
            )
            vals.setdefault("base_service_code", base)
            if not vals.get("service_code") or "/" not in vals.get("service_code", ""):
                number = vals.get("client_file_sequence") or self._next_litigation_case_number(base)
                vals["client_file_sequence"] = number
                level_code = self._litigation_level_code(vals) or "F"
                vals["service_code"] = "%s/%02d/%s" % (base, number, level_code)
            return vals
        vals.setdefault(
            "service_code",
            self._legal_service_base_from_vals(vals)
            or self.env["qlk.client.file"]._next_legal_service_code(service_code, company),
        )
        return vals

    def _legal_service_base_from_vals(self, vals):
        base = vals.get("base_service_code") or self.env.context.get("default_base_service_code")
        if base:
            return base
        service_code = vals.get("service_code")
        if service_code:
            return service_code.split("/", 1)[0]
        project = self.env["qlk.project"].browse(vals.get("project_id"))
        if project.exists() and project.service_code:
            return project.service_code.split("/", 1)[0]
        return False

    def _next_litigation_case_number(self, base_service_code):
        cases = self.env["qlk.case"].sudo().search(
            [
                "|",
                ("base_service_code", "=", base_service_code),
                ("service_code", "=ilike", "%s/%%" % base_service_code),
            ]
        )
        numbers = []
        for case in cases:
            if case.client_file_sequence:
                numbers.append(case.client_file_sequence)
                continue
            service_code = case.service_code or ""
            parts = service_code.split("/")
            if len(parts) > 1 and parts[1].isdigit():
                numbers.append(int(parts[1]))
        return (max(numbers) if numbers else 0) + 1

    def _build_client_file_service_code(self, client_file, vals, service_code):
        self._apply_service_code_defaults(vals, service_code, client_file.company_id)
        return vals.get("service_code")

    def _litigation_level_code(self, vals):
        level = self.env["litigation.level"]
        if vals.get("litigation_level_id"):
            level = level.browse(vals["litigation_level_id"])
        elif vals.get("litigation_degree_id"):
            degree = self.env["qlk.litigation.degree"].browse(vals["litigation_degree_id"])
            level = degree.level_id
        if not level:
            level = self.env.ref("qlk_management.litigation_level_first_instance", raise_if_not_found=False)
        xmlid = level.get_external_id().get(level.id) if level else False
        return LEVEL_XMLID_CODES.get(xmlid) or level.code if level else False

    def _copy_client_file_attachments(self, records, normal_field="attachment_ids", translation_field=False):
        for record in records:
            client_file = record.client_file_id
            if not client_file:
                continue
            normal, translation = client_file._collect_transfer_attachments()
            if normal_field in record._fields and normal:
                record[normal_field] = [(4, attachment_id) for attachment_id in normal.ids]
            if translation_field and translation_field in record._fields and translation:
                record[translation_field] = [(4, attachment_id) for attachment_id in translation.ids]
            elif normal_field in record._fields and translation:
                record[normal_field] = [(4, attachment_id) for attachment_id in translation.ids]


class QlkCaseClientFile(models.Model):
    _name = "qlk.case"
    _inherit = ["qlk.case", "qlk.client.file.service.mixin"]

    client_file_id = fields.Many2one("qlk.client.file", string="Client File", ondelete="set null", index=True, tracking=True)
    client_file_sequence = fields.Integer(readonly=True, copy=False)
    base_service_code = fields.Char(string="Base Service Code", readonly=True, copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("client_file_id") and not vals.get("project_id"):
                self._apply_client_file_defaults(vals, "litigation")
            else:
                self._apply_service_code_defaults(vals, "litigation")
            vals.setdefault("client_file_sequence", self._sequence_from_service_code(vals.get("service_code")))
        records = super(QlkCaseClientFile, self.with_context(skip_engagement_case_validation=True)).create(vals_list)
        self._copy_client_file_attachments(records, "attachment_ids")
        return records

    def _apply_client_file_partner_defaults(self, vals, client_file, engagement):
        vals.setdefault("client_id", client_file.partner_id.id)
        vals.setdefault("client_ids", [(6, 0, client_file.partner_id.ids)])
        if engagement and engagement.lawyer_employee_id:
            vals.setdefault("employee_id", engagement.lawyer_employee_id.id)
        if engagement and engagement.litigation_degree_ids and not vals.get("litigation_degree_id"):
            degree = engagement.litigation_degree_ids[:1]
            vals["litigation_degree_id"] = degree.id
            vals["litigation_level_id"] = degree.level_id.id if degree.level_id else False
        vals.setdefault("litigation_flow", "litigation")
        return vals

    @api.model
    def _sequence_from_service_code(self, service_code):
        if not service_code or "/" not in service_code:
            return 0
        parts = service_code.split("/")
        return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0


class PreLitigationClientFile(models.Model):
    _name = "qlk.pre.litigation"
    _inherit = ["qlk.pre.litigation", "qlk.client.file.service.mixin"]

    client_file_id = fields.Many2one("qlk.client.file", string="Client File", ondelete="set null", index=True, tracking=True)
    client_file_sequence = fields.Integer(readonly=True, copy=False)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_pre_litigation_attachment_rel",
        "pre_litigation_id",
        "attachment_id",
        string="Attachments",
        tracking=True,
    )

    @api.model
    def create(self, vals):
        if vals.get("client_file_id") and not vals.get("project_id"):
            self._apply_client_file_defaults(vals, "pre_litigation")
        else:
            self._apply_service_code_defaults(vals, "pre_litigation")
        record = super(PreLitigationClientFile, self.with_context(skip_engagement_service_validation=True)).create(vals)
        self._copy_client_file_attachments(record, "attachment_ids", "translation_attachment_ids")
        return record

    def _apply_client_file_partner_defaults(self, vals, client_file, engagement):
        vals.setdefault("client_id", client_file.partner_id.id)
        if engagement and engagement.lawyer_employee_id:
            vals.setdefault("lawyer_employee_id", engagement.lawyer_employee_id.id)
        vals.setdefault("subject", client_file.name)
        return vals


class ArbitrationCaseClientFile(models.Model):
    _name = "qlk.arbitration.case"
    _inherit = ["qlk.arbitration.case", "qlk.client.file.service.mixin"]

    client_file_id = fields.Many2one("qlk.client.file", string="Client File", ondelete="set null", index=True, tracking=True)
    client_file_sequence = fields.Integer(readonly=True, copy=False)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_arbitration_case_attachment_rel",
        "arbitration_case_id",
        "attachment_id",
        string="Attachments",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("client_file_id") and not vals.get("project_id"):
                self._apply_client_file_defaults(vals, "arbitration")
            else:
                self._apply_service_code_defaults(vals, "arbitration")
        records = super(ArbitrationCaseClientFile, self.with_context(skip_engagement_service_validation=True)).create(vals_list)
        self._copy_client_file_attachments(records, "attachment_ids")
        return records

    def _apply_client_file_partner_defaults(self, vals, client_file, engagement):
        vals.setdefault("claimant_id", client_file.partner_id.id)
        if engagement and engagement.lawyer_employee_id:
            vals.setdefault("responsible_employee_id", engagement.lawyer_employee_id.id)
        return vals


class CorporateCaseClientFile(models.Model):
    _name = "qlk.corporate.case"
    _inherit = ["qlk.corporate.case", "qlk.client.file.service.mixin"]

    client_file_id = fields.Many2one("qlk.client.file", string="Client File", ondelete="set null", index=True, tracking=True)
    client_file_sequence = fields.Integer(readonly=True, copy=False)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "qlk_corporate_case_attachment_rel",
        "corporate_case_id",
        "attachment_id",
        string="Attachments",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("client_file_id") and not vals.get("project_id"):
                self._apply_client_file_defaults(vals, "corporate")
            else:
                self._apply_service_code_defaults(vals, "corporate")
        records = super(CorporateCaseClientFile, self.with_context(skip_engagement_service_validation=True)).create(vals_list)
        self._copy_client_file_attachments(records, "attachment_ids")
        return records

    def _apply_client_file_partner_defaults(self, vals, client_file, engagement):
        vals.setdefault("client_id", client_file.partner_id.id)
        if engagement and engagement.lawyer_employee_id:
            vals.setdefault("responsible_employee_id", engagement.lawyer_employee_id.id)
        return vals
