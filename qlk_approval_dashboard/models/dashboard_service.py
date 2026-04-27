# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError
from odoo.osv import expression


class QlkApprovalDashboard(models.AbstractModel):
    _name = "qlk.approval.dashboard"
    _description = "Approval Dashboard Service"

    DASHBOARD_ACCESS_GROUPS = (
        "qlk_approval_dashboard.group_qlk_approval_dashboard_user",
        "qlk_approval_dashboard.group_qlk_approval_dashboard_manager",
        "qlk_management.group_bd_user",
        "qlk_management.group_bd_manager",
        "qlk_management.group_el_user",
        "qlk_management.group_el_manager",
        "qlk_management.group_pre_litigation_user",
        "qlk_management.group_pre_litigation_manager",
        "qlk_corporate.group_corporate_user",
        "qlk_corporate.group_corporate_manager",
        "qlk_arbitration.group_arbitration_user",
        "qlk_arbitration.group_arbitration_manager",
    )
    DASHBOARD_MANAGER_GROUPS = (
        "qlk_approval_dashboard.group_qlk_approval_dashboard_manager",
        "qlk_management.group_bd_manager",
        "qlk_management.group_el_manager",
        "qlk_management.group_pre_litigation_manager",
        "base.group_system",
        "qlk_corporate.group_corporate_manager",
        "qlk_arbitration.group_arbitration_manager",
    )
    RECORD_LIMIT = 10
    STATE_FIELD_NAMES = ("state", "approval_state", "status")
    PENDING_STATES = {
        "waiting_manager_approval",
        "waiting_client_approval",
        "waiting_approval",
        "waiting",
        "pending",
    }
    APPROVED_STATES = {"approved_manager", "approved_client", "approved"}
    REJECTED_STATES = {"rejected"}
    APPROVE_METHODS = (
        "action_client_approve",
        "action_manager_approve",
        "action_approve",
        "button_approve",
    )
    REJECT_METHODS = (
        "action_client_reject",
        "action_manager_reject",
        "action_reject",
        "button_reject",
    )

    def _has_existing_group(self, xmlid):
        group = self.env.ref(xmlid, raise_if_not_found=False)
        return bool(group and group.id in self.env.user._get_group_ids())

    def _has_any_existing_group(self, group_xmlids):
        return any(self._has_existing_group(xmlid) for xmlid in group_xmlids)

    def _ensure_dashboard_access(self):
        if not self._has_any_existing_group(self.DASHBOARD_ACCESS_GROUPS):
            raise AccessError(_("You do not have access to the approval dashboard."))

    def _is_manager(self):
        return self._has_any_existing_group(self.DASHBOARD_MANAGER_GROUPS)

    def _all_approval_states(self):
        return self.PENDING_STATES | self.APPROVED_STATES | self.REJECTED_STATES

    def _selection_values(self, model, field):
        selection = field.selection
        try:
            if isinstance(selection, str):
                selection = getattr(model, selection)()
            elif callable(selection):
                selection = selection(model)
        except Exception:
            return set()
        return {value for value, _label in selection or [] if value}

    def _state_info(self, model):
        best = False
        all_states = self._all_approval_states()
        for field_name in self.STATE_FIELD_NAMES:
            field = model._fields.get(field_name)
            if not field or field.type != "selection":
                continue
            values = self._selection_values(model, field)
            matched = values & all_states
            if matched and (not best or len(matched) > len(best["values"])):
                best = {
                    "field": field_name,
                    "values": matched,
                    "pending": matched & self.PENDING_STATES,
                    "approved": matched & self.APPROVED_STATES,
                    "rejected": matched & self.REJECTED_STATES,
                    "labels": dict(field.selection or []) if isinstance(field.selection, (list, tuple)) else {},
                }
        return best

    def _has_decision_methods(self, model):
        has_approve = any(hasattr(model, method) for method in self.APPROVE_METHODS)
        has_reject = any(hasattr(model, method) for method in self.REJECT_METHODS) or hasattr(
            model, "_apply_rejection_reason"
        )
        return has_approve and has_reject

    def _has_acl_group_gate(self, model_name):
        access = self.env["ir.model.access"]
        if not access.check(model_name, "read", False):
            return False
        ir_model = self.env["ir.model"].sudo()._get(model_name)
        if not ir_model:
            return False
        acl_records = access.sudo().search([("model_id", "=", ir_model.id), ("perm_read", "=", True)])
        if not acl_records:
            return True
        if acl_records.filtered(lambda acl: not acl.group_id):
            return True
        user_group_ids = set(self.env.user._get_group_ids())
        acl_group_ids = set(acl_records.mapped("group_id").ids)
        return bool(user_group_ids & acl_group_ids)

    def _can_view_model(self, model_name):
        if model_name not in self.env:
            return False
        model = self.env[model_name]
        if getattr(model, "_abstract", False) or getattr(model, "_transient", False):
            return False
        if not self._has_acl_group_gate(model_name):
            return False
        try:
            model.check_access_rights("read")
        except AccessError:
            return False
        return True

    def _approval_model_configs(self):
        configs = []
        for model_name in sorted(self.env.registry.models):
            if model_name.startswith(("base.", "bus.", "ir.", "mail.", "res.", "web.")):
                continue
            if model_name not in self.env or not self._can_view_model(model_name):
                continue
            model = self.env[model_name]
            state_info = self._state_info(model)
            if not state_info or not self._has_decision_methods(model):
                continue
            configs.append(
                {
                    "model": model_name,
                    "label": model._description or model_name,
                    "state": state_info,
                }
            )
        return configs

    @api.model
    def has_visible_approval_model(self):
        self._ensure_dashboard_access()
        return bool(self._approval_model_configs())

    def _team_employee_ids(self):
        user = self.env.user
        employees = user.employee_ids
        if not employees and getattr(user, "employee_id", False):
            employees = user.employee_id
        if not employees or "hr.employee" not in self.env:
            return []
        employee_model = self.env["hr.employee"]
        domain = expression.OR(
            [
                [("id", "in", employees.ids)],
                [("parent_id", "in", employees.ids)],
            ]
        )
        return employee_model.search(domain).ids

    def _scoped_domain(self, model_name, scope):
        if scope == "all" and self._is_manager():
            return []

        model = self.env[model_name]
        user = self.env.user
        employee_ids = user.employee_ids.ids
        if getattr(user, "employee_id", False):
            employee_ids = list(set(employee_ids + [user.employee_id.id]))
        if scope == "team" and self._is_manager():
            employee_ids = self._team_employee_ids() or employee_ids

        user_domains = []
        for field_name in (
            "reviewer_id",
            "user_id",
            "owner_id",
            "assigned_user_id",
            "lawyer_user_id",
            "requested_by",
            "approval_requested_by",
            "create_uid",
        ):
            field = model._fields.get(field_name)
            if field and field.type == "many2one" and field.comodel_name == "res.users":
                user_domains.append([(field_name, "=", user.id)])

        for field_name in ("employee_id", "responsible_employee_id", "lawyer_employee_id"):
            field = model._fields.get(field_name)
            if employee_ids and field and field.type == "many2one" and field.comodel_name == "hr.employee":
                user_domains.append([(field_name, "in", employee_ids)])

        for field_name in ("employee_ids", "assigned_employee_ids", "lawyer_ids"):
            field = model._fields.get(field_name)
            if employee_ids and field and field.type == "many2many" and field.comodel_name == "hr.employee":
                user_domains.append([(field_name, "in", employee_ids)])

        return expression.OR(user_domains) if user_domains else [("id", "=", 0)]

    def _safe_count(self, model, domain):
        try:
            model.check_access_rights("read")
            return model.search_count(domain)
        except AccessError:
            return 0

    def _state_domain(self, state_info, bucket):
        states = state_info.get(bucket) or set()
        if not states:
            return [("id", "=", 0)]
        return [(state_info["field"], "in", sorted(states))]

    def _records_domain(self, state_info):
        return [(state_info["field"], "in", sorted(state_info["values"]))]

    def _action_dict(self, model_name, name, domain=None, context=None):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model_name,
            "view_mode": "list,form",
            "views": [[False, "list"], [False, "form"]],
            "domain": domain or [],
            "context": context or {},
            "target": "current",
        }

    def _first_rel_name(self, record, field_names):
        for field_name in field_names:
            if field_name not in record._fields:
                continue
            value = record[field_name]
            if value:
                return value.display_name
        return ""

    def _record_hours(self, record):
        for field_name in ("hours_spent", "total_hours", "planned_hours", "effective_hours", "unit_amount"):
            if field_name in record._fields:
                return float(record[field_name] or 0.0)
        return 0.0

    def _record_state_payload(self, record, state_info):
        field_name = state_info["field"]
        value = record[field_name]
        if value in self.PENDING_STATES:
            category = "pending"
        elif value in self.APPROVED_STATES:
            category = "approved"
        elif value in self.REJECTED_STATES:
            category = "rejected"
        else:
            category = "neutral"
        return {
            "value": value,
            "label": state_info.get("labels", {}).get(value, value or ""),
            "category": category,
        }

    def _record_can_decide(self, record, state_info):
        if record[state_info["field"]] not in self.PENDING_STATES:
            return False
        if "can_approve" in record._fields:
            try:
                return bool(record.can_approve)
            except AccessError:
                return False
        try:
            record.check_access_rights("write")
            record.check_access_rule("write")
        except AccessError:
            return False
        return self._is_manager()

    def _record_payload(self, record, config):
        state_info = config["state"]
        can_decide = self._record_can_decide(record, state_info)
        return {
            "id": record.id,
            "model": record._name,
            "name": record.display_name,
            "client": self._first_rel_name(
                record,
                ("partner_id", "client_id", "customer_id", "contact_id", "commercial_partner_id", "company_id"),
            ),
            "assigned_user": self._first_rel_name(
                record,
                (
                    "reviewer_id",
                    "assigned_user_id",
                    "user_id",
                    "owner_id",
                    "lawyer_user_id",
                    "requested_by",
                    "create_uid",
                    "employee_id",
                    "responsible_employee_id",
                    "lawyer_employee_id",
                ),
            ),
            "status": self._record_state_payload(record, state_info),
            "hours": round(self._record_hours(record), 2),
            "can_approve": can_decide,
            "can_reject": can_decide,
        }

    def _order_for_model(self, model):
        for order in ("write_date desc, id desc", "create_date desc, id desc", "id desc"):
            fields = {part.split()[0] for part in order.split(", ")}
            if fields <= set(model._fields):
                return order
        return "id desc"

    def _section_payload(self, config, scope):
        model = self.env[config["model"]]
        scope_domain = self._scoped_domain(config["model"], scope)
        state_info = config["state"]
        pending_domain = expression.AND([scope_domain, self._state_domain(state_info, "pending")])
        approved_domain = expression.AND([scope_domain, self._state_domain(state_info, "approved")])
        rejected_domain = expression.AND([scope_domain, self._state_domain(state_info, "rejected")])
        all_domain = expression.AND([scope_domain, self._records_domain(state_info)])
        pending = self._safe_count(model, pending_domain)
        approved = self._safe_count(model, approved_domain)
        rejected = self._safe_count(model, rejected_domain)
        return {
            "model": config["model"],
            "label": config["label"],
            "state_field": state_info["field"],
            "counts": {
                "pending": pending,
                "approved": approved,
                "rejected": rejected,
                "total": pending + approved + rejected,
            },
            "domains": {
                "pending": pending_domain,
                "approved": approved_domain,
                "rejected": rejected_domain,
                "all": all_domain,
            },
            "action": self._action_dict(config["model"], config["label"], all_domain),
        }

    def _active_records_payload(self, config, scope):
        model = self.env[config["model"]]
        domain = expression.AND([self._scoped_domain(config["model"], scope), self._records_domain(config["state"])])
        records = model.search(domain, order=self._order_for_model(model), limit=self.RECORD_LIMIT)
        return [self._record_payload(record, config) for record in records]

    def _hours_payload(self, scope):
        if "qlk.task" in self.env and self._can_view_model("qlk.task"):
            model = self.env["qlk.task"]
            amount_field = "hours_spent"
            user_field = "assigned_user_id" if "assigned_user_id" in model._fields else "reviewer_id"
            domain = self._scoped_domain("qlk.task", scope)
            if "approval_state" in model._fields:
                domain = expression.AND([domain, [("approval_state", "=", "approved")]])
        elif "account.analytic.line" in self.env and self._can_view_model("account.analytic.line"):
            model = self.env["account.analytic.line"]
            amount_field = "unit_amount"
            user_field = "user_id" if "user_id" in model._fields else False
            domain = self._scoped_domain("account.analytic.line", scope)
        else:
            return {"total": 0.0, "by_user": [], "model": False, "domain": []}

        if not user_field:
            total_group = model.read_group(domain, [amount_field], [], lazy=False)
            total = round(float(total_group[0].get(amount_field) or 0.0), 2) if total_group else 0.0
            return {"total": total, "by_user": [], "model": model._name, "domain": domain}

        try:
            groups = model.read_group(domain, [amount_field, user_field], [user_field], lazy=False)
        except AccessError:
            groups = []
        rows = []
        total = 0.0
        for group in groups:
            ref = group.get(user_field)
            hours = round(float(group.get(amount_field) or 0.0), 2)
            total += hours
            if not ref:
                continue
            user_domain = expression.AND([domain, [(user_field, "=", ref[0])]])
            rows.append(
                {
                    "user_id": ref[0],
                    "name": ref[1],
                    "hours": hours,
                    "domain": user_domain,
                    "action": self._action_dict(model._name, _("Approved Hours"), user_domain),
                }
            )
        rows.sort(key=lambda item: item["hours"], reverse=True)
        return {
            "total": round(total, 2),
            "by_user": rows[:10],
            "model": model._name,
            "domain": domain,
            "action": self._action_dict(model._name, _("Approved Hours"), domain),
        }

    @api.model
    def get_dashboard_data(self, scope="mine", active_model=False):
        self._ensure_dashboard_access()
        if scope == "all" and not self._is_manager():
            scope = "mine"

        configs = self._approval_model_configs()
        sections = [self._section_payload(config, scope) for config in configs]
        config_by_model = {config["model"]: config for config in configs}

        if active_model not in config_by_model:
            active_model = sections[0]["model"] if sections else False

        approvals = {}
        if active_model:
            approvals[active_model] = self._active_records_payload(config_by_model[active_model], scope)

        pending_total = sum(section["counts"]["pending"] for section in sections)
        approved_total = sum(section["counts"]["approved"] for section in sections)
        rejected_total = sum(section["counts"]["rejected"] for section in sections)
        hours = self._hours_payload(scope)

        permissions = {
            "is_manager": self._is_manager(),
            "can_use_all": self._is_manager(),
            "can_view_module": bool(sections),
            "models": {
                section["model"]: {
                    "can_view_module": True,
                    "can_approve": bool(section["counts"]["pending"]),
                }
                for section in sections
            },
        }

        return {
            "scope": scope,
            "active_model": active_model,
            "kpis": {
                "pending": {"label": _("Pending Approvals"), "value": pending_total, "tone": "warning"},
                "approved": {"label": _("Approved"), "value": approved_total, "tone": "success"},
                "rejected": {"label": _("Rejected"), "value": rejected_total, "tone": "danger"},
                "hours": {"label": _("Total Hours"), "value": hours["total"], "tone": "primary"},
            },
            "approvals": approvals,
            "sections": sections,
            "hours": hours,
            "permissions": permissions,
        }

    @api.model
    def get_pending_count(self):
        self._ensure_dashboard_access()
        data = self.get_dashboard_data(scope="mine")
        return data.get("kpis", {}).get("pending", {}).get("value", 0)

    def _approve_method(self, record, state_value):
        if state_value == "waiting_client_approval" and hasattr(record, "action_client_approve"):
            return record.action_client_approve
        if state_value == "waiting_manager_approval" and hasattr(record, "action_manager_approve"):
            return record.action_manager_approve
        for method_name in self.APPROVE_METHODS:
            if hasattr(record, method_name):
                return getattr(record, method_name)
        return False

    def _reject_method(self, record, state_value):
        if state_value == "waiting_client_approval" and hasattr(record, "action_client_reject"):
            return record.action_client_reject
        if state_value in ("waiting_manager_approval", "approved_manager") and hasattr(record, "action_manager_reject"):
            return record.action_manager_reject
        for method_name in self.REJECT_METHODS:
            if hasattr(record, method_name):
                return getattr(record, method_name)
        return False

    @api.model
    def action_decide(self, model_name, res_id, decision, reason=False):
        self._ensure_dashboard_access()
        config = next((item for item in self._approval_model_configs() if item["model"] == model_name), False)
        if not config:
            raise AccessError(_("You cannot access this approval model."))

        record = self.env[model_name].browse(int(res_id)).exists()
        if not record:
            raise UserError(_("The approval record no longer exists."))
        record.check_access_rights("read")
        record.check_access_rule("read")

        state_info = config["state"]
        state_value = record[state_info["field"]]
        if state_value not in self.PENDING_STATES:
            raise UserError(_("Only pending records can be approved or rejected."))
        if not self._record_can_decide(record, state_info):
            raise AccessError(_("You are not allowed to approve or reject this record."))

        if decision == "approve":
            method = self._approve_method(record, state_value)
            if not method:
                raise UserError(_("No approval method is available for this record."))
            return method() or {"type": "ir.actions.client", "tag": "reload"}

        if decision == "reject":
            if hasattr(record, "_apply_rejection_reason") and reason:
                role = "client" if state_value == "waiting_client_approval" else "manager"
                record._apply_rejection_reason(reason, role)
                return {"type": "ir.actions.client", "tag": "reload"}
            method = self._reject_method(record, state_value)
            if not method:
                raise UserError(_("No rejection method is available for this record."))
            try:
                return method(reason) or {"type": "ir.actions.client", "tag": "reload"}
            except TypeError:
                return method() or {"type": "ir.actions.client", "tag": "reload"}

        raise UserError(_("Unsupported approval decision."))
