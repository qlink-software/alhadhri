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

    get summaryCards() {
        return this.state.data?.summary || [];
    }

    get pipeline() {
        return (
            this.state.data?.pipeline || {
                records: [],
                action: null,
                domain: [],
                title: _t("Pipeline Watch"),
            }
        );
    }

    get agreements() {
        return (
            this.state.data?.agreements || {
                records: [],
                action: null,
                title: _t("Recently Signed"),
            }
        );
    }

    get documents() {
        return (
            this.state.data?.documents || {
                records: [],
                action: null,
                domain: [],
                title: _t("Document Alerts"),
            }
        );
    }

    get followups() {
        return (
            this.state.data?.followups || {
                items: [],
                action: null,
                domain: [],
                title: _t("Follow-ups"),
            }
        );
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

BusinessDevelopmentDashboard.template = "qlk_project_management.BDDashboard";

registry.category("actions").add("qlk.bd.dashboard", BusinessDevelopmentDashboard);
