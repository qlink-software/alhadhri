/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class BusinessDevelopmentDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, data: null });
        this.openAction = this.openAction.bind(this);
        this.openRecord = this.openRecord.bind(this);

        onWillStart(async () => {
            try {
                const payload = await this.orm.call("qlk.bd.dashboard", "get_dashboard_data", []);
                this.state.data = payload;
            } catch (error) {
                console.error("Failed to load BD dashboard", error);
                this.notification.add(_t("Failed to load the BD dashboard"), {
                    type: "danger",
                });
            } finally {
                this.state.loading = false;
            }
        });
    }

    get palette() {
        return this.state.data?.palette || {};
    }

    get kpis() {
        return (
            this.state.data?.kpis || {
                opportunities: 0,
                proposals: 0,
                engagements: 0,
                projects: 0,
            }
        );
    }

    get sections() {
        return this.state.data?.sections || [];
    }

    formatNumber(value) {
        if (value === undefined || value === null) {
            return "0";
        }
        return Intl.NumberFormat().format(value);
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

BusinessDevelopmentDashboard.template = "qlk_management.BDDashboard";

registry.category("actions").add("qlk.bd.dashboard", BusinessDevelopmentDashboard);
