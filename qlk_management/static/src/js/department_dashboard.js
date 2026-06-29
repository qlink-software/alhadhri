/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class DepartmentDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            data: {
                cards: [],
                projects: [],
                project_states: [],
                matters: [],
                tasks: [],
                schedule: { items: [] },
                labels: {
                    loading: _t("Loading your workspace…"),
                    access_denied: _t("Access denied"),
                },
                user: {},
                palette: {},
            },
        });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "qlk.department.dashboard",
                "get_dashboard_data",
                [this.constructor.department]
            );
        } catch (error) {
            this.notification.add(_t("Unable to load your department dashboard."), {
                type: "danger",
            });
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    get data() {
        return this.state.data || {};
    }

    get palette() {
        return this.data.palette || {};
    }

    get labels() {
        return this.data.labels || {};
    }

    get scheduleItems() {
        return this.data.schedule?.items || [];
    }

    formatCount(value) {
        return Number(value || 0).toLocaleString();
    }

    formatHours(value) {
        return Number(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        });
    }

    cloneDomain(domain) {
        return domain ? JSON.parse(JSON.stringify(domain)) : [];
    }

    openAction(actionMeta, domain = []) {
        if (!actionMeta?.id) {
            return;
        }
        this.action.doAction(actionMeta.id, {
            additional_domain: this.cloneDomain(domain),
        });
    }

    openCard(card) {
        this.openAction(card?.action, card?.domain);
    }

    openProjectState(state) {
        this.openAction(this.data.projects_action, state?.domain);
    }

    openRecord(record) {
        const url = record?.url;
        if (!url?.res_model || !url?.res_id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: url.res_model,
            res_id: url.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

DepartmentDashboard.template = "qlk_management.DepartmentDashboard";

class CorporateDashboard extends DepartmentDashboard {}
CorporateDashboard.department = "corporate";

class ArbitrationDashboard extends DepartmentDashboard {}
ArbitrationDashboard.department = "arbitration";

registry.category("actions").add("qlk_corporate_dashboard", CorporateDashboard);
registry.category("actions").add("qlk_arbitration_dashboard", ArbitrationDashboard);
