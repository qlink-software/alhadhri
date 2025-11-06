/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class CorporateDashboard extends Component {
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
                const payload = await this.orm.call("qlk.corporate.dashboard", "get_dashboard_data", []);
                this.state.data = payload;
            } catch (error) {
                console.error("Failed to load corporate dashboard", error);
                this.notification.add(_t("Failed to load corporate dashboard"), {
                    type: "danger",
                });
                throw error;
            } finally {
                this.state.loading = false;
            }
        });
    }

    get palette() {
        return this.state.data?.palette || {};
    }

    get metrics() {
        return (
            this.state.data?.metrics || {
                cases_total: 0,
                cases_today: 0,
                cases_week: 0,
                consultations_today: 0,
                consultations_week: 0,
                contracts_week: 0,
                documents_week: 0,
                hours_total: 0,
                hours_week: 0,
                hours_today: 0,
                week_range: { start: "", end: "" },
                today_label: "",
            }
        );
    }

    get lists() {
        return (
            this.state.data?.lists || {
                recent_cases: [],
                upcoming_consultations: [],
                recent_contracts: [],
                recent_documents: [],
            }
        );
    }

    get userInfo() {
        return this.state.data?.user || {};
    }

    get isManager() {
        return Boolean(this.state.data?.is_manager);
    }

    formatHours(hours) {
        if (hours === undefined || hours === null) {
            return "0.00";
        }
        return Number(hours).toFixed(2);
    }

    openAction(actionKey) {
        const actionMeta = this.state.data?.actions?.[actionKey];
        if (!actionMeta?.id) {
            return;
        }
        this.action.doAction(actionMeta.id);
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

CorporateDashboard.template = "qlk_law_dashboard.CorporateDashboard";

registry.category("actions").add("qlk.corporate.dashboard", CorporateDashboard);
