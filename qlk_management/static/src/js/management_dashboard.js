/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

class ManagementDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            data: null,
        });

        onWillStart(async () => {
            try {
                const payload = await this.orm.call("qlk.management.dashboard", "get_dashboard_data", []);
                this.state.data = payload;
            } catch (error) {
                console.error("Failed to load BD dashboard", error);
                this.notification.add(_t("Unable to load BD dashboard"), { type: "danger" });
                throw error;
            } finally {
                this.state.loading = false;
            }
        });
    }

    get palette() {
        return this.state.data?.palette || {};
    }

    get hero() {
        return this.state.data?.hero || {
            clients: 0,
            proposals: 0,
            approved_proposals: 0,
            engagements: 0,
            documents: 0,
        };
    }

    get proposals() {
        return (
            this.state.data?.proposals || {
                total: 0,
                approved: 0,
                waiting: 0,
                billable: 0,
                collected: 0,
                pending: 0,
                action: null,
                reports: [],
            }
        );
    }

    get engagements() {
        return (
            this.state.data?.engagements || {
                total: 0,
                waiting: 0,
                types: [],
                action: null,
            }
        );
    }

    get alerts() {
        return (
            this.state.data?.alerts || {
                expiring: [],
                missing: [],
            }
        );
    }

    get pipeline() {
        return (
            this.state.data?.pipeline || {
                total: 0,
                open: 0,
                won: 0,
                stages: [],
                action: null,
            }
        );
    }

    get clients() {
        return (
            this.state.data?.clients || {
                total: 0,
                with_documents: 0,
                documents_total: 0,
                expiring: [],
                action: null,
                documents_action: null,
            }
        );
    }

    formatNumber(value) {
        if (value === undefined || value === null) {
            return "0";
        }
        return Intl.NumberFormat().format(value);
    }

    formatCurrency(value) {
        if (value === undefined || value === null) {
            return "0.00";
        }
        return Number(value).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    openAction(actionMeta, domain = null) {
        if (!actionMeta?.id) {
            return;
        }
        const options = {};
        if (domain && domain.length) {
            options.domain = domain;
        }
        this.action.doAction(actionMeta.id, options);
    }

    openRecord(link) {
        if (!link?.res_model || !link?.res_id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: link.res_model,
            res_id: link.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

ManagementDashboard.template = "qlk_management.ManagementDashboard";

registry.category("actions").add("qlk_management_dashboard", ManagementDashboard);
